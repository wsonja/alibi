"""The scripted performer (docs/INTERFACES.md §5).

A deterministic, rule-based actor that plays a suspect from its own case data alone.  It is the offline experience
and the per-turn fallback when Gemini is unavailable, and it obeys exactly the same isolation rule as the Gemini
performer: it only ever sees its own PerformContext (this suspect's persona, goals, knowledge, secrets, deflections
and state).  Nothing else exists from its point of view.

Design notes
------------
* Every choice with more than one acceptable answer is made with a RNG seeded from suspect id + turn + message,
  so a replayed game is reproducible while different questions get different phrasing.
* Case text is written in the third person ("She was in the garden").  ``first_person`` rewrites it as the suspect
  speaking, using the suspect's own pronoun gender so that other people's pronouns survive ("He saw her" -> "He saw
  me" for Ada).
* Deflections are written as stage descriptions ("Asks whether the detective has spoken to Mr. Pell yet").
  ``render_deflection`` turns them into lines of dialogue.
* Whatever the rules produce, the final line is regex-checked against every LOCKED secret's ``key_phrases`` and
  replaced on a hit (rule 9).
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any

from .suspect import build_system_blocks

log = logging.getLogger("alibi.agents.scripted")

MAX_SENTENCES = 4

# --------------------------------------------------------------------------------------------------------------------
# Text utilities
# --------------------------------------------------------------------------------------------------------------------

_ABBREVIATIONS = ("Mr", "Mrs", "Ms", "Dr", "St", "Sr", "Jr", "Prof", "Capt", "Col", "Lt", "Sgt", "Rev", "Hon")
_SENT_SPLIT_RE = re.compile(
    "".join(rf"(?<!\b{a}\.)" for a in _ABBREVIATIONS) + r"(?<=[.!?…])[\"'”’)]?\s+(?=[\"'“‘(]?[A-Z…\-—])"
)
_QUOTE_RE = re.compile(r"(?<![A-Za-z])'([^']+?)'(?![A-Za-z])")


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, keeping 'Mr.' / 'Dr.' and ellipses intact."""
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENT_SPLIT_RE.split(text)]
    return [p for p in parts if p]


def count_sentences(text: str) -> int:
    return len(split_sentences(text))


def limit_sentences(text: str, n: int = MAX_SENTENCES) -> str:
    parts = split_sentences(text)
    if len(parts) <= n:
        return " ".join(parts)
    return " ".join(parts[:n])


def ensure_terminal(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return text
    if text[-1] not in ".!?…\"'”’":
        text += "."
    return text


def capitalise(text: str) -> str:
    text = text.lstrip()
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1 :]
        if ch not in "…\"'“‘(-—":
            break
    return text


STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "that", "this", "those", "these", "there", "here",
    "of", "to", "in", "on", "at", "by", "for", "from", "with", "without", "into", "onto", "upon", "about", "over",
    "under", "after", "before", "during", "until", "till", "since", "as", "is", "am", "are", "was", "were", "be",
    "been", "being", "do", "does", "did", "done", "doing", "have", "has", "had", "having", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must", "not", "no", "nor", "so", "such", "very", "just", "only",
    "even", "also", "too", "quite", "rather", "really", "still", "yet", "again", "ever", "never", "always", "often",
    "already", "all", "any", "some", "each", "every", "either", "neither", "both", "few", "more", "most", "much",
    "many", "little", "less", "least", "own", "same", "other", "another", "which", "what", "who", "whom", "whose",
    "where", "when", "why", "how", "i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", "it",
    "its", "itself", "they", "them", "their", "theirs", "themselves", "one", "ones", "oneself", "someone", "anyone",
    "everyone", "nobody", "something", "anything", "everything", "nothing", "say", "says", "said", "tell", "tells",
    "told", "ask", "asks", "asked", "know", "knows", "knew", "think", "thinks", "thought", "want", "wants",
    "wanted", "go", "goes", "went", "come", "comes", "came", "get", "gets", "got", "make", "makes", "made", "take",
    "takes", "took", "see", "sees", "seen", "saw", "look", "looks", "looked", "give", "gives", "gave", "find",
    "finds", "found", "put", "puts", "let", "lets", "keep", "keeps", "kept", "mean", "means", "meant", "seem",
    "seems", "seemed", "well", "now", "once", "yes", "please", "sir", "madam", "inspector",
    "detective", "mr", "mrs", "dr", "lady", "miss", "ma'am", "thing", "things", "way", "ways", "word", "words",
    "true", "actually", "perhaps", "maybe", "bit", "lot", "far", "thank", "thanks", "good",
    "right", "wrong", "fine", "like",
}

# Synonym groups: stems that count as the same topic word.  Keys are the topic labels used in prose.
SYNONYM_GROUPS: dict[str, list[str]] = {
    "the garden": ["garden", "terrace", "outsid", "bench", "yew", "ground", "lawn", "outdoor"],
    "the telephone": ["telephon", "phone", "ring", "rang", "call", "line", "villag"],
    "the cigars": ["cigar", "smok", "tobacco", "mantelpiec"],
    "the dismissal": ["sack", "dismiss", "referenc", "charact", "notic", "wage", "insolenc", "fire", "employ"],
    "the study door": ["glove", "corridor", "wastebasket", "waste", "passag"],
    "the poison": ["poison", "cyanid", "decant", "brandi", "almond", "darkroom", "chemic", "fix", "potassium", "drink"],
    "the money": [
        "embezzl", "money", "account", "ledger", "manchest", "partnership", "thief", "steal", "stole", "skim",
        "debt", "pound", "fraud", "solicitor", "dissol", "polic", "restitut", "discrepanc", "book", "figur",
    ],
    "the affair": ["affair", "lover", "franc", "romanc", "mistress", "elop", "love"],
    "the heart": ["heart", "angina", "cardiac", "collaps", "natur"],
    "bed": ["bed", "upstair", "headach", "asleep", "sleep", "retir"],
    "the kitchen": ["kitchen", "coffee", "servant", "scullery"],
    "the necklace": ["necklac", "pearl", "clasp", "jewel"],
    "the argument": ["argu", "quarrel", "row", "shout", "thursday"],
    "the study": ["study", "desk", "drawer"],
    "the letter": ["letter", "solicitor", "unsent"],
}
_STEM_TO_GROUP: dict[str, str] = {}
for _label, _stems in SYNONYM_GROUPS.items():
    for _st in _stems:
        _STEM_TO_GROUP.setdefault(_st, _label)
_GROUP_ORDER = list(SYNONYM_GROUPS)


def stem(word: str) -> str:
    w = word.lower()
    for suf in ("ing", "ies", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)] + ("y" if suf == "ies" else "")
            break
    return w


def canon(word: str) -> str:
    st = stem(word)
    if st in _STEM_TO_GROUP:
        return _STEM_TO_GROUP[st]
    for g_stem, label in _STEM_TO_GROUP.items():
        if len(g_stem) >= 4 and st.startswith(g_stem):
            return label
    return st


_TIME_WORDS = {
    0: "{h} o'clock", 5: "five past {h}", 10: "ten past {h}", 15: "quarter past {h}", 20: "twenty past {h}",
    25: "twenty-five past {h}", 30: "half past {h}", 35: "twenty-five to {n}", 40: "twenty to {n}",
    45: "quarter to {n}", 50: "ten to {n}", 55: "five to {n}",
}
_HOUR_WORDS = {
    0: "midnight", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
    9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
}


def spell_time(hh: int, mm: int) -> str:
    """'23:20' -> 'twenty past eleven' so numeric times match spoken ones."""
    hh = hh % 24
    h12 = hh % 12
    h_word = "midnight" if hh == 0 else _HOUR_WORDS.get(h12 if h12 else 12, str(h12))
    nxt = (hh + 1) % 24
    n_word = "midnight" if nxt == 0 else _HOUR_WORDS.get(nxt % 12 if nxt % 12 else 12, str(nxt))
    rounded = int(round(mm / 5.0) * 5) % 60
    if mm == 0:
        return h_word
    return _TIME_WORDS.get(rounded, "{h}").format(h=h_word, n=n_word)


def normalise_times(text: str) -> str:
    return re.sub(r"\b(\d{1,2})[:.](\d{2})\b", lambda m: spell_time(int(m.group(1)), int(m.group(2))), text)


def content_tokens(text: str) -> list[str]:
    text = normalise_times(text or "")
    words = re.findall(r"[A-Za-z][A-Za-z'\-]+", text)
    out = []
    for w in words:
        lw = w.lower().strip("'-")
        if len(lw) < 3 or lw in STOPWORDS:
            continue
        out.append(canon(lw))
    return out


def regex_words(pattern: str) -> list[str]:
    """The literal words inside a key_phrases regex (for topic scoring)."""
    return [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", pattern or "") if w.lower() not in STOPWORDS]


def stable_seed(*parts: Any) -> int:
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:12], 16)


# --------------------------------------------------------------------------------------------------------------------
# Names, gender and the first-person transform
# --------------------------------------------------------------------------------------------------------------------

HONORIFICS_MALE = ("Mr", "Mr.", "Sir", "Lord", "Master", "Captain", "Colonel", "Major", "Reverend", "Father")
HONORIFICS_FEMALE = ("Mrs", "Mrs.", "Miss", "Ms", "Ms.", "Lady", "Madame", "Mademoiselle", "Sister", "Dame")
HONORIFICS_ANY = ("Dr", "Dr.", "Professor", "Prof.", "Nurse", "Judge")
ALL_HONORIFICS = HONORIFICS_MALE + HONORIFICS_FEMALE + HONORIFICS_ANY
_HON_KEYS_MALE = {h.rstrip(".") + "." for h in HONORIFICS_MALE}
_HON_KEYS_FEMALE = {h.rstrip(".") + "." for h in HONORIFICS_FEMALE}
_HON_KEYS_ALL = {h.rstrip(".") + "." for h in ALL_HONORIFICS}

_SENTENCE_STARTERS = {
    "when", "at", "the", "on", "in", "nobody", "everyone", "after", "before", "if", "then", "there", "this", "that",
    "it", "they", "we", "you", "he", "she", "his", "her", "a", "an", "hers", "about", "by", "for",
    "from", "with", "without", "into", "during", "until", "since", "as", "because", "although", "though", "while",
    "whether", "once", "what", "where", "who", "why", "how", "nothing", "something", "someone", "anyone",
    "everything", "last", "next", "tonight", "today", "yesterday", "all", "both", "each", "every", "some", "any",
    "no", "not", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "twenty", "thirty",
    "half", "quarter",
}

_ROLE_NOUN_RE = re.compile(
    r"\b(?:the|a|an|that|this|our|their|your|some|any|every|no)\s+(?:old\s+|young\s+|poor\s+|good\s+|dead\s+)?"
    r"(?:doctor|physician|maid|housemaid|butler|footman|cook|inspector|detective|solicitor|policeman|constable|nurse|"
    r"man|woman|girl|boy|gentleman|lady|guest|patient|servant|wife|husband|partner|host|hostess|victim|body|fellow|"
    r"stranger|visitor|mother|father|brother|sister|son|daughter|uncle|aunt|nephew|niece|cousin|friend|master|mistress|"
    r"employer|colonel|major|captain|vicar|priest|chauffeur|gardener|secretary|valet|governess|nanny|actress|actor)\b",
    re.IGNORECASE,
)


def split_name(name: str) -> tuple[str | None, list[str]]:
    """('Dr.', ['Elias', 'Crane']) for 'Dr. Elias Crane'."""
    tokens = (name or "").replace(",", " ").split()
    if tokens and tokens[0].rstrip(".") + "." in _HON_KEYS_ALL:
        return tokens[0], tokens[1:]
    return None, tokens


def gender_from_honorific(name: str) -> str | None:
    hon, _ = split_name(name)
    if not hon:
        return None
    key = hon.rstrip(".") + "."
    if key in _HON_KEYS_MALE:
        return "he"
    if key in _HON_KEYS_FEMALE:
        return "she"
    return None


def name_variants(name: str) -> list[str]:
    """Every way a person might be referred to, longest first: 'Dr. Elias Crane', 'Dr. Crane', 'Elias', 'Crane'."""
    hon, parts = split_name(name)
    variants: set[str] = set()
    if not parts:
        return [name] if name else []
    full = " ".join(parts)
    variants.add(full)
    if hon:
        variants.add(f"{hon} {full}")
        variants.add(f"{hon} {parts[-1]}")
        variants.add(f"{hon} {parts[0]}")
        variants.add(f"{hon.rstrip('.')} {parts[-1]}")
        variants.add(f"{hon.rstrip('.')} {parts[0]}")
    variants.add(parts[0])
    if len(parts) > 1:
        variants.add(parts[-1])
        variants.add(f"{parts[0]} {parts[-1]}")
    return sorted((v for v in variants if v), key=len, reverse=True)


def infer_gender(suspect: dict) -> str:
    """'she' or 'he' — from an explicit field, the honorific, or pronoun counts in the secrets/persona/knowledge."""
    explicit = str(suspect.get("gender") or suspect.get("pronouns") or "").lower()
    if explicit.startswith(("f", "she", "her", "w")):
        return "she"
    if explicit.startswith(("m", "he", "him")):
        return "he"
    g = gender_from_honorific(suspect.get("name", ""))
    if g:
        return g
    she = he = 0
    # sentence-initial pronouns in secret texts are the strongest signal (they are written about the suspect)
    for sec in suspect.get("secrets", []):
        for sent in split_sentences(sec.get("text", "")):
            first = sent.split(" ", 1)[0].strip(".,;:").lower()
            if first == "she":
                she += 3
            elif first == "he":
                he += 3
    corpus = " ".join([suspect.get("persona", "")] + list(suspect.get("knowledge", [])))
    she += len(re.findall(r"\b(she|her|hers|herself)\b", corpus, re.IGNORECASE))
    he += len(re.findall(r"\b(he|him|his|himself)\b", corpus, re.IGNORECASE))
    return "she" if she >= he else "he"


_ME_CUES = {
    "saw", "see", "sees", "seen", "with", "to", "at", "for", "from", "of", "about", "told", "tell", "tells", "near",
    "by", "against", "between", "behind", "beside", "towards", "toward", "after", "before", "like", "unlike",
    "than", "upon", "into", "onto", "without", "meet", "met", "watched", "watch", "heard", "hear", "hears",
    "warned", "warn", "asked", "ask", "asks", "blame", "blamed", "blames", "suspect", "suspected", "accuse",
    "accused", "remind", "reminded", "reminds", "pay", "paid", "paying", "give", "gave", "given", "show", "showed",
    "shown", "hurt", "help", "helped", "treat", "treated", "treating", "trust", "trusted", "despise", "despised",
    "loved", "love", "loves", "hate", "hated", "kill", "killed", "threaten", "threatened", "dismissed", "dismiss",
    "sacked", "left", "leave", "leaving", "let",
}

_CONJUGATE = {
    "is": "am", "was": "was", "has": "have", "does": "do", "doesn't": "don't", "isn't": "am not",
    "hasn't": "haven't", "wasn't": "wasn't",
}
_NO_STRIP = {
    "was", "is", "has", "does", "this", "thus", "yes", "plus", "its", "us", "as", "less", "unless", "perhaps", "always",
    "across", "his", "hers", "ours", "gas", "bus", "sometimes", "besides", "afterwards", "towards", "upstairs",
    "downstairs", "series", "species", "news", "means", "alas",
}
_ADVERBS = ("only", "never", "always", "just", "really", "simply", "still", "also", "rather", "hardly", "barely", "certainly", "honestly", "privately")
_OBJECT_NEXT = {
    "to", "in", "at", "on", "and", "that", "of", "for", "with", "there", "then", "as", "but", "so", "if", "when",
    "up", "down", "out", "off", "a", "an", "the", "again", "alone", "away", "back", "nothing", "anything",
    "something", "yesterday", "today", "tonight", "this", "last", "into", "about", "from", "by", "because", "after",
    "before", "until", "over", "under", "once", "twice", "quietly", "gently", "kindly", "directly", "straight",
    "home", "upstairs", "downstairs", "outside", "inside", "nor", "or",
}


def _first_person_verb(word: str) -> str:
    lw = word.lower()
    if lw in _CONJUGATE:
        out = _CONJUGATE[lw]
        return out if word.islower() else out.capitalize()
    if lw in _NO_STRIP or len(lw) < 4 or not lw.endswith("s") or lw.endswith("ss"):
        return word
    if lw.endswith("ies"):
        return word[:-3] + "y"
    if lw.endswith(("oes", "shes", "ches", "sses", "xes", "zes")):
        return word[:-2]
    return word[:-1]


def _fix_agreement(text: str) -> str:
    """'I brings' -> 'I bring', 'I is' -> 'I am', 'I doesn't' -> 'I don't'."""
    adverb_alt = "|".join(_ADVERBS)

    def repl(m: re.Match) -> str:
        adverb = m.group(1) or ""
        verb = m.group(2)
        return f"I {adverb}{_first_person_verb(verb)}"

    return re.sub(rf"\bI ((?:{adverb_alt}) )?([A-Za-z']+)", repl, text)


_CLAUSE_SPLIT_RE = re.compile(
    r"(,\s+|;\s+|:\s+|\s+and\s+|\s+but\s+|\s+because\s+|\s+that\s+|\s+when\s+|\s+while\s+|\s+if\s+|\s+although\s+|"
    r"\s+though\s+|\s+so\s+|\s+where\s+|\s+which\s+|\s+who\s+|\s+—\s+|\s+-\s+)"
)


@dataclass
class Person:
    name: str
    variants: list[str]
    gender: str | None  # "she" | "he" | None


def _detect_names(sentence: str, others: list[Person]) -> list[tuple[int, str | None]]:
    """(position, gender) of every other person mentioned in the sentence."""
    found: list[tuple[int, str | None]] = []
    for p in others:
        for v in p.variants:
            for m in re.finditer(rf"(?<![A-Za-z]){re.escape(v)}(?![A-Za-z])", sentence):
                found.append((m.start(), p.gender))
    # honorific + Capitalised word (e.g. 'Sir Reginald') and clause-initial capitalised words (e.g. 'Reginald reminded')
    hon_alt = "|".join(re.escape(h) for h in ALL_HONORIFICS)
    for m in re.finditer(rf"\b({hon_alt})\s+([A-Z][a-z]+)", sentence):
        key = m.group(1).rstrip(".") + "."
        g = "he" if key in _HON_KEYS_MALE else ("she" if key in _HON_KEYS_FEMALE else None)
        found.append((m.start(), g))
    for m in re.finditer(r"(?:^|[,;:]\s+|\band\s+|\bbut\s+)([A-Z][a-z]{2,})\b", sentence):
        word = m.group(1)
        if word.lower() in _SENTENCE_STARTERS or word in ("I", "One") or word.rstrip(".") + "." in _HON_KEYS_ALL:
            continue
        found.append((m.start(1), None))
    return sorted(found, key=lambda x: x[0])


_UNIT_SPLIT_RE = re.compile("".join(rf"(?<!\b{a}\.)" for a in _ABBREVIATIONS) + r"(?<=[.!?…])\s+(?=[\"'“‘(]?[A-Z…])")


def _role_positions(sentence: str) -> list[int]:
    return [m.start() for m in _ROLE_NOUN_RE.finditer(sentence)]


def first_person(
    text: str,
    suspect: dict,
    cast_names: dict[str, str] | None = None,
    gender: str | None = None,
    *,
    transform_objects: bool = True,
) -> str:
    """Rewrite third-person case text as the suspect speaking.

    Rules (see module docstring): the suspect's own name -> I/me/my; only pronouns of the suspect's own gender are
    touched; a same-gender pronoun that follows another person's name in the sentence is left alone; object
    pronouns in a clause whose subject is the suspect are someone else ("He had warned him" -> "I had warned him");
    'They' after a 'with <Name>' sentence becomes 'We'; verbs are re-conjugated after a new 'I'.
    ``transform_objects=False`` leaves object pronouns alone (used for deflections, where "found him" is the body).
    """
    if not text:
        return ""
    try:
        return _first_person(text, suspect, cast_names or {}, gender or infer_gender(suspect), transform_objects)
    except Exception as exc:  # noqa: BLE001 - never let a transform bug take a turn down
        log.warning("first_person failed (%s); using naive transform", exc)
        return _naive_first_person(text, gender or "she")


def _naive_first_person(text: str, gender: str) -> str:
    if gender == "she":
        text = re.sub(r"\bShe\b", "I", text)
        text = re.sub(r"\bshe\b", "I", text)
        text = re.sub(r"\bherself\b", "myself", text, flags=re.IGNORECASE)
        text = re.sub(r"\bher\b(?=\s+[a-z])", "my", text, flags=re.IGNORECASE)
        text = re.sub(r"\bher\b", "me", text, flags=re.IGNORECASE)
    else:
        text = re.sub(r"\bHe\b", "I", text)
        text = re.sub(r"\bhe\b", "I", text)
        text = re.sub(r"\bhimself\b", "myself", text, flags=re.IGNORECASE)
        text = re.sub(r"\bhis\b", "my", text, flags=re.IGNORECASE)
        text = re.sub(r"\bhim\b", "me", text, flags=re.IGNORECASE)
    return _fix_agreement(text)


def _replace_own_name(text: str, self_name: str) -> str:
    _hon, parts = split_name(self_name)
    surname = parts[-1] if len(parts) > 1 else None
    for v in name_variants(self_name):
        pat = re.compile(rf"(?<![A-Za-z]){re.escape(v)}(?![A-Za-z])")
        bare_surname = surname is not None and v == surname

        def sub(m: re.Match, bare=bare_surname) -> str:
            before = m.string[: m.start()]
            after = m.string[m.end():]
            if bare and re.search(r"\b(Sir|Lady|Lord|Mr\.?|Mrs\.?|Miss|Dr\.?)\s+[A-Z][a-z]+\s*$", before):
                return m.group(0)  # 'Sir Reginald Vane' is someone else
            if after.startswith("'s"):
                return "my\x01"
            prev = re.findall(r"[A-Za-z']+", before[-40:])
            prev_word = prev[-1].lower() if prev else ""
            if prev_word in _ME_CUES:
                return "me"
            return "I"

        text = pat.sub(sub, text)
    return text.replace("my\x01's", "my").replace("my\x01", "my")


@dataclass
class _SentenceScope:
    """Everything the pronoun rules need to know about the sentence being rewritten."""

    sent: str
    gender: str
    names: list[tuple[int, str | None]]
    roles: list[int]
    quoted_spans: list[tuple[int, int]]
    starts_with_self: bool
    transform_objects: bool
    transformed_self: bool = False

    def other_before(self, abs_pos: int, include_roles: bool = False) -> bool:
        if any(npos < abs_pos and g in (None, self.gender) for npos, g in self.names):
            return True
        return include_roles and any(rp < abs_pos for rp in self.roles)

    def in_quotes(self, abs_pos: int) -> bool:
        return any(a <= abs_pos < b for a, b in self.quoted_spans)


def _rewrite_pronoun(m: re.Match, scope: _SentenceScope, piece_start: int, clause_subject_self: bool) -> str:
    subj, obj, poss, refl = ("she", "her", "her", "herself") if scope.gender == "she" else ("he", "him", "his", "himself")
    word = m.group(0)
    lw = word.lower()
    abs_pos = piece_start + m.start()
    cap = word[0].isupper()
    if scope.in_quotes(abs_pos):
        return word
    tail = scope.sent[abs_pos + len(word):]
    if lw in ("her", "his") and re.match(r"\s+(ladyship|lordship|majesty|grace)\b", tail, re.IGNORECASE):
        return word
    if lw == refl:
        if scope.other_before(abs_pos, include_roles=True) and not scope.starts_with_self:
            return word
        return "Myself" if cap else "myself"
    if lw == subj:
        if scope.starts_with_self or not scope.other_before(abs_pos):
            scope.transformed_self = True
            return "I"
        return word
    if scope.gender == "she" and lw == "her":
        nxt = re.match(r"\s*([A-Za-z']+|[.,;:!?]|$)", tail)
        nxt_word = (nxt.group(1) if nxt else "").lower()
        is_object = nxt_word in _OBJECT_NEXT or nxt_word == "" or not nxt_word.isalpha()
        if is_object:
            if clause_subject_self or not scope.transform_objects:
                return word
            return "Me" if cap else "me"
        if scope.starts_with_self or not scope.other_before(abs_pos, include_roles=True):
            return "My" if cap else "my"
        return word
    if lw == obj:  # him / her-as-object: someone else when this clause's subject is the suspect
        if clause_subject_self or not scope.transform_objects:
            return word
        return "Me" if cap else "me"
    if lw == poss:  # his
        if scope.starts_with_self or not scope.other_before(abs_pos, include_roles=True):
            return "My" if cap else "my"
        return word
    return word


def _rewrite_sentence(sent: str, others: list[Person], gender: str, transform_objects: bool, prev_with_self: bool) -> tuple[str, bool]:
    """Rewrite one sentence; returns (text, ends_with_self_and_'with') for the They->We rule."""
    subj = "she" if gender == "she" else "he"
    pronoun_re = re.compile(r"\b(she|her|herself)\b" if gender == "she" else r"\b(he|him|his|himself)\b", re.IGNORECASE)
    # They -> We after a 'with <name>' sentence about the suspect
    if prev_with_self and re.match(r"^\W*They\b", sent):
        sent = re.sub(r"^(\W*)They\b", r"\1We", sent)
        sent = re.sub(r"\btheir\b", "our", sent)
        sent = re.sub(r"\bthem\b", "us", sent)
        sent = re.sub(r"\bthemselves\b", "ourselves", sent)
    scope = _SentenceScope(
        sent=sent,
        gender=gender,
        names=_detect_names(sent, others),
        roles=_role_positions(sent),
        quoted_spans=[(m.start(), m.end()) for m in _QUOTE_RE.finditer(sent)],
        starts_with_self=bool(re.match(rf"^\W*({subj}|I)\b", sent, re.IGNORECASE)),
        transform_objects=transform_objects,
    )
    pos = 0
    new_pieces = []
    for piece in _CLAUSE_SPLIT_RE.split(sent):
        piece_start = pos
        pos += len(piece)
        if _CLAUSE_SPLIT_RE.fullmatch(piece):
            new_pieces.append(piece)
            continue
        clause_subject_self = bool(re.match(rf"^\W*({subj}|I)\b", piece, re.IGNORECASE))
        new_pieces.append(
            pronoun_re.sub(lambda m, ps=piece_start, cs=clause_subject_self: _rewrite_pronoun(m, scope, ps, cs), piece)
        )
    out = "".join(new_pieces)
    return out, scope.transformed_self and bool(re.search(r"\bwith\b", out))


def _first_person(text: str, suspect: dict, cast_names: dict[str, str], gender: str, transform_objects: bool = True) -> str:
    self_id = suspect.get("id")
    others = [Person(n, name_variants(n), gender_from_honorific(n)) for sid, n in cast_names.items() if sid != self_id and n]
    text = _replace_own_name(text, suspect.get("name", ""))
    out_sentences: list[str] = []
    prev_with_self = False
    for sent in _UNIT_SPLIT_RE.split(text):
        rewritten, prev_with_self = _rewrite_sentence(sent, others, gender, transform_objects, prev_with_self)
        out_sentences.append(rewritten)
    return _fix_agreement(" ".join(out_sentences))


# --------------------------------------------------------------------------------------------------------------------
# Deflections: stage descriptions -> dialogue
# --------------------------------------------------------------------------------------------------------------------

_DET = r"the (?:detective|inspector|officer|constable|sergeant|investigator|police|policeman|cop)"
_YOU_FORMS = [
    (re.compile(rf"\b{_DET} has considered\b", re.IGNORECASE), "have you considered"),
    (re.compile(rf"\b{_DET} has\b", re.IGNORECASE), "have you"),
    (re.compile(rf"\b{_DET} will be\b", re.IGNORECASE), "will you be"),
    (re.compile(rf"\b{_DET} will\b", re.IGNORECASE), "will you"),
    (re.compile(rf"\b{_DET} is\b", re.IGNORECASE), "are you"),
    (re.compile(rf"\b{_DET} was\b", re.IGNORECASE), "were you"),
    (re.compile(rf"\b{_DET} would\b", re.IGNORECASE), "would you"),
    (re.compile(rf"\b{_DET} might\b", re.IGNORECASE), "might you"),
    (re.compile(rf"\b{_DET} should\b", re.IGNORECASE), "should you"),
    (re.compile(rf"\b{_DET} can\b", re.IGNORECASE), "can you"),
    (re.compile(rf"\b{_DET}'s\b", re.IGNORECASE), "your"),
    (re.compile(rf"\b{_DET}\b", re.IGNORECASE), "you"),
]
_ASIDE_THAT_RE = re.compile(r"^,?\s*([^,]{1,40}?),\s*that\s+(.*)$", re.DOTALL)
_STAGE_TAIL_RE = re.compile(
    r",?\s+(then|and then)\s+(looks?|glances?|stares?|laughs?|smiles?|pauses?|sighs?|shrugs?|frowns?|falls? silent|"
    r"goes? quiet|adds? nothing)[^.]*\.?$",
    re.IGNORECASE,
)
_AUX_START_RE = re.compile(r"^(have|will|are|were|would|might|do|did|can|could|should|is|has) you\b", re.IGNORECASE)


def _you_forms(text: str) -> str:
    for pat, repl in _YOU_FORMS:
        text = pat.sub(repl, text)
    return text


def _strip_quotes(text: str) -> str:
    return _QUOTE_RE.sub(r"\1", text)


def render_deflection(desc: str, suspect: dict, cast_names: dict[str, str], gender: str, rng: random.Random) -> tuple[str, str]:
    """Turn 'Asks whether the detective has spoken to Mr. Pell yet, and mentions that ...' into dialogue.

    Returns (spoken, tell) — a trailing stage direction ('then looks as if she wishes she hadn't') becomes the tell.
    """
    desc = (desc or "").strip()
    tell = ""
    m = _STAGE_TAIL_RE.search(desc)
    if m:
        tell = m.group(0).strip(" ,.")
        tell = re.sub(r"^(then|and then)\s+", "", tell, flags=re.IGNORECASE)
        desc = desc[: m.start()].rstrip(" ,")
    if not desc:
        return "", tell

    parts = re.split(
        r",\s+and\s+(?=(?:mentions?|adds?|says?|remarks?|notes?|asks?|wonders?|points? out|suggests?)\b)", desc, maxsplit=1
    )
    sentences = [_render_clause(part, suspect, cast_names, gender, rng) for part in parts]
    spoken = " ".join(s for s in sentences if s)
    return spoken, tell


_VERB_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(?:asks?|enquires?|inquires?)(?:,\s*([^,]+),)?\s+(?:whether|if)\s+(.*)$", re.IGNORECASE | re.DOTALL), "ask"),
    (re.compile(r"^(?:asks?|enquires?|inquires?)(?:,\s*([^,]+),)?\s+(why|how|what|where|when|who)\s+(.*)$", re.IGNORECASE | re.DOTALL), "ask_wh"),
    (re.compile(r"^wonders?(?: aloud)?\s+(why|how|what|where|whether|if|who)\s+(.*)$", re.IGNORECASE | re.DOTALL), "wonder"),
    (re.compile(r"^(?:says?|states?|insists?|claims?|protests?|declares?|replies?|answers?)(?:,?\s*(?:quietly|flatly|coldly|firmly|gently|softly|simply|stiffly),?)?\s+(?:that\s+)?(.*)$", re.IGNORECASE | re.DOTALL), "say"),
    (re.compile(r"^(?:suggests?|recommends?|urges?|advises?|proposes?)\s+(.*)$", re.IGNORECASE | re.DOTALL), "suggest"),
    (re.compile(r"^(?:mentions?|adds?|notes?|observes?|remarks?|points? out|hints?)(?:\s+(?:gently|quietly|lightly|drily|dryly|casually|carefully|pointedly|softly|coldly|mildly))?\s+(?:that\s+)?(.*)$", re.IGNORECASE | re.DOTALL), "mention"),
    (re.compile(r"^reminds?\s+(?:the\s+)?(?:detective|inspector|them|him|her)\s+(?:that\s+)?(.*)$", re.IGNORECASE | re.DOTALL), "remind"),
    (re.compile(r"^(?:talks?|speaks?|goes? on|rambles?)\s+(?:at length\s+)?about\s+(.*)$", re.IGNORECASE | re.DOTALL), "talk"),
    (re.compile(r"^tells?\s+(?:a\s+)?(?:long\s+|rambling\s+|funny\s+)?(?:story|anecdote|tale)\s+about\s+(.*)$", re.IGNORECASE | re.DOTALL), "story"),
    (re.compile(r"^(?:changes? the subject to|turns? the conversation to|brings? up)\s+(.*)$", re.IGNORECASE | re.DOTALL), "talk"),
    (re.compile(r"^(?:complains?|grumbles?)\s+(?:that\s+|about\s+)?(.*)$", re.IGNORECASE | re.DOTALL), "complain"),
    (re.compile(r"^(?:denies?|refuses?)\s+(.*)$", re.IGNORECASE | re.DOTALL), "deny"),
    (re.compile(r"^(?:laughs?|smiles?|shrugs?)(?:\s+and\s+)?\s*(?:says?\s+)?(?:that\s+)?(.*)$", re.IGNORECASE | re.DOTALL), "say"),
]


def _render_clause(part: str, suspect: dict, cast_names: dict[str, str], gender: str, rng: random.Random) -> str:
    part = part.strip().rstrip(".")
    if not part:
        return ""

    def fp(t: str) -> str:
        return first_person(t, suspect, cast_names, gender, transform_objects=False)

    for pat, kind in _VERB_PATTERNS:
        m = pat.match(part)
        if not m:
            continue
        groups = list(m.groups())
        if kind == "ask":
            aside, rest = groups[0], groups[1]
            rest = _strip_quotes(_you_forms(rest))
            if not _AUX_START_RE.match(rest):
                rest = re.sub(r"^you (have|will|are|were|would|might|do|did|can|could|should)\b", r"\1 you", rest, flags=re.IGNORECASE)
                if not _AUX_START_RE.match(rest):
                    rest = "have you considered whether " + rest
            q = capitalise(fp(rest)) + "?"
            if aside:
                q = capitalise(aside.strip()) + ", " + q[0].lower() + q[1:]
            return q
        if kind == "ask_wh":
            aside, wh, rest = groups[0], groups[1], groups[2]
            rest = _strip_quotes(_you_forms(rest))
            q = f"{wh.capitalize()} {fp(rest)}?"
            if aside:
                q = capitalise(aside.strip()) + ", " + q[0].lower() + q[1:]
            return q
        if kind == "wonder":
            wh, rest = groups[0], groups[1]
            rest = _strip_quotes(_you_forms(rest))
            opener = rng.choice(["I do wonder", "One does wonder", "I can't help wondering", "I have been wondering"])
            return f"{opener} {wh.lower()} {fp(rest)}."
        if kind in ("say", "mention"):
            rest = _strip_quotes(_you_forms(groups[-1]))
            aside = _ASIDE_THAT_RE.match(rest)
            if aside:  # 'Says, to be honest, that she ...' -> 'To be honest, I ...'
                rest = f"{aside.group(1).strip()}, {aside.group(2)}"
            rest = re.sub(r"(,?)\s+and that\s+", r"\1 and ", rest)
            return ensure_terminal(capitalise(fp(rest)))
        if kind == "suggest":
            rest = _strip_quotes(groups[-1])
            rest = re.sub(rf"^(?:that\s+)?(?:{_DET}|you)\s+(?:should\s+|ought to\s+|might\s+)?", "", rest, flags=re.IGNORECASE)
            opener = rng.choice(["Perhaps you should", "You might", "If I were you I would"])
            return ensure_terminal(f"{opener} {fp(_you_forms(rest))}")
        if kind == "remind":
            body = fp(_strip_quotes(_you_forms(groups[-1])))
            opener = rng.choice(["May I remind you that", "You will recall that", "I would remind you that"])
            return ensure_terminal(f"{opener} {body[0].lower() + body[1:] if body else body}")
        if kind == "talk":
            body = fp(_strip_quotes(groups[-1]))
            opener = rng.choice(["I keep thinking about", "One should remember", "You must understand about", "It all comes back to"])
            return ensure_terminal(f"{opener} {body}")
        if kind == "story":
            body = fp(_strip_quotes(groups[-1]))
            opener = rng.choice(["That reminds me of", "Did I ever tell you about", "You should have seen the business of"])
            end = "?" if opener.startswith("Did") else "."
            return f"{opener} {body.rstrip('.')}{end}"
        if kind == "complain":
            body = fp(_strip_quotes(groups[-1]))
            return ensure_terminal(f"Frankly, {body[0].lower() + body[1:] if body else body}")
        if kind == "deny":
            body = fp(_strip_quotes(groups[-1]))
            return ensure_terminal(f"I deny {body}")
    # unknown shape: speak it directly in the first person
    return ensure_terminal(capitalise(fp(_strip_quotes(_you_forms(part)))))


# --------------------------------------------------------------------------------------------------------------------
# Voice: what the speech_quirk tells us
# --------------------------------------------------------------------------------------------------------------------

_ADDRESS_TERMS = {
    "sir", "madam", "ma'am", "my friend", "inspector", "detective", "officer", "constable", "my dear", "old man",
    "my lord", "my lady", "dear lady", "old boy", "old chap", "my good man", "young man", "miss",
}


@dataclass
class Voice:
    address: str | None = None
    uses_one: bool = False
    medical: bool = False
    questions: bool = False
    formal: bool = False
    clipped: bool = False
    solicitor: bool = False
    warm: bool = False
    exact: bool = False  # "answers exactly what is asked"
    tics: list[str] = field(default_factory=list)  # complete sentences quoted in the quirk
    phrases: list[str] = field(default_factory=list)  # lowercase multiword phrases quoted in the quirk

    def suffix(self) -> str:
        return f", {self.address}" if self.address else ""


def parse_voice(quirk: str) -> Voice:
    v = Voice()
    q = quirk or ""
    ql = q.lower()
    quotes = _QUOTE_RE.findall(q) + re.findall(r"\"([^\"]+)\"", q) + re.findall(r"‘([^’]+)’", q)
    addresses: list[str] = []
    for quote in quotes:
        cleaned = quote.strip().strip(".,!?")
        low = cleaned.lower()
        if low in _ADDRESS_TERMS:
            addresses.append(low)
            continue
        m = re.match(r"^([A-Za-z' ]+?),\s*\1$", cleaned)  # 'Inspector, Inspector'
        if m and m.group(1).lower() in _ADDRESS_TERMS:
            addresses.append(m.group(1).lower())
            continue
        words = cleaned.split()
        if len(words) >= 3 and cleaned[0].isupper():
            v.tics.append(ensure_terminal(cleaned))
        elif len(words) >= 2:
            v.phrases.append(low)
    if "detective's title" in ql or "your title" in ql or "by title" in ql:
        addresses.insert(0, "inspector")
    if addresses:
        v.address = addresses[0]
        if v.address == "inspector":
            v.address = "Inspector"
    v.uses_one = bool(re.search(r"'one'|\bone\b instead of\b|says 'one'", ql))
    v.medical = "medical" in ql or "euphemism" in ql
    v.questions = "with questions" in ql or "with a question" in ql
    v.formal = "formal" in ql
    v.clipped = "clipped" in ql or "short sentences" in ql or "not a word more" in ql
    v.solicitor = "solicitor" in ql or "lawyer" in ql
    v.warm = "warm" in ql or "familiar" in ql or "expansive" in ql
    v.exact = "exactly what is asked" in ql or "not a word more" in ql
    return v


def other_address(other_name: str, rel_type: str, speaker_voice: Voice) -> str:
    """How this suspect addresses the other in a confrontation: 'Elias', 'Dr. Crane', 'Lady Margaret', 'Pell'."""
    hon, parts = split_name(other_name)
    if not parts:
        return other_name
    warm = rel_type in {"lover", "ally", "trusts", "kind_to", "family", "friend"}
    if hon:
        h = hon.rstrip(".")
        if h in ("Lady", "Sir", "Lord", "Dame"):
            return f"{hon} {parts[0]}"
        if warm and not speaker_voice.formal:
            return parts[0]
        return f"{hon} {parts[-1]}"
    if warm or rel_type in {"employer"}:
        return parts[0]
    if speaker_voice.formal and speaker_voice.address in ("sir", "madam", "ma'am") and rel_type in {"fears", "threatens", "employer", "acquaintance", ""}:
        return speaker_voice.address  # a servant does not address a guest by surname
    return parts[-1] if len(parts) > 1 else parts[0]


# --------------------------------------------------------------------------------------------------------------------
# The performer
# --------------------------------------------------------------------------------------------------------------------

WHEREABOUTS_RE = re.compile(
    r"\bwhere (were|was) you\b|\bwhere did you go\b|\bwhereabouts\b|\bwhat were you doing\b|\bwhere you were\b|"
    r"\bwhere you went\b|\baccount for (your|the) (time|movements|evening)\b|\byour movements\b|\bwhere exactly\b",
    re.IGNORECASE,
)
MESSAGE_PREFIX_RE = re.compile(r"^(Detective(?: \([a-z]+\))?:|The detective shows you:)\s*", re.IGNORECASE)
_SUSPICION_RE = re.compile(
    r"\b(saw|seen|came in|come out|wet|lie|lied|lying|argu\w*|quarrel\w*|threaten\w*|took|stole|stolen|angry|secret\w*|"
    r"hiding|hid|sneak\w*|crept|creeping|lovers?|gloves?|cold to|dismiss\w*|sack\w*|owe[sd]?|debt|not (certain|sure) what)\b",
    re.IGNORECASE,
)


def strip_message_prefix(msg: str, cast_names: dict[str, str] | None = None) -> str:
    msg = (msg or "").strip()
    m = MESSAGE_PREFIX_RE.match(msg)
    if m:
        return msg[m.end():].strip()
    for name in (cast_names or {}).values():
        if msg.startswith(name + ":"):
            return msg[len(name) + 1 :].strip()
    return msg


_LABEL_VERBS = {
    "leave", "come", "put", "take", "stay", "ring", "call", "fetch", "pull", "walk", "talk", "speak", "meet", "help",
    "kill", "steal", "hide", "burn", "watch", "wait", "return", "enter", "open", "close", "lock", "break", "hear",
    "recognize", "recognise", "smell", "tell", "answer", "confirm", "deny", "admit", "intend", "plan", "mean", "need",
    "want", "seem", "feel", "wear", "carry", "bring", "send", "write", "read", "sign", "borrow", "lend", "owe", "pay",
}


def topic_label(text: str, key_phrases: str = "", names: dict[str, str] | None = None) -> str | None:
    """A short noun phrase naming what a piece of text is about, drawn from the text itself ('the garden').

    Candidate words are the text's own content words minus names and verbs; words that also appear in the
    key_phrases regex count double; ties go to the longer word.  Proper nouns keep their capital and lose the 'the'.
    """
    name_words: set[str] = set()
    for n in (names or {}).values():
        name_words |= {w.lower() for w in re.findall(r"[A-Za-z]+", n)}
    key_stems = {stem(w.lower()) for w in regex_words(key_phrases)}
    counts: dict[str, tuple[int, str]] = {}
    for word in re.findall(r"[A-Za-z][A-Za-z'\-]+", text or ""):
        lw = word.lower().strip("'-")
        st = stem(lw)
        if len(lw) < 4 or lw in STOPWORDS or lw in name_words or st in _LABEL_VERBS or lw in _LABEL_VERBS:
            continue
        if lw.endswith(("ed", "ing", "ly")) and lw not in ("bed", "wedding", "evening", "morning", "shilling", "ceiling", "building"):
            continue
        if word[0].isupper() and word.rstrip(".") + "." in _HON_KEYS_ALL:
            continue
        score = 1 + (2 if st in key_stems else 0)
        prev = counts.get(st)
        counts[st] = (prev[0] + score if prev else score, prev[1] if prev else word)
    if not counts:
        return None
    best = max(counts.items(), key=lambda kv: (kv[1][0], len(kv[0])))
    word = best[1][1]
    if word[0].isupper():
        return word
    return f"the {word.lower()}"


def secret_label(sec: dict, suspect: dict, cast_names: dict[str, str], gender: str) -> str:
    """A short phrase naming the secret's topic, for reasoning / private messages ('the garden')."""
    label = topic_label(sec.get("text", ""), sec.get("key_phrases", ""), cast_names)
    if label:
        return label
    fp = first_person(sec.get("text", ""), suspect, cast_names, gender)
    words = fp.split()
    return " ".join(words[:6]).rstrip(".,;") + ("…" if len(words) > 6 else "")


class ScriptedPerformer:
    mode = "scripted"

    async def perform(self, ctx: dict) -> dict[str, Any]:
        ctx["system_blocks"] = build_system_blocks(ctx)
        try:
            return Turn(ctx).run()
        except Exception:
            log.exception("scripted performer failed")
            suspect = ctx.get("suspect") or {}
            return {
                "spoken": "I have told you everything I can.",
                "internal_reasoning": "Something went wrong in my head; I said as little as possible.",
                "honesty": "evasive",
                "emotion": "nervous",
                "stress_delta": 0,
                "reveals": [],
                "accuses": None,
                "wants_to_tell": [],
                "tell": (suspect.get("tells") or {}).get("nervous", ""),
            }


class Turn:
    """All the state for one scripted turn.  Built from ctx only."""

    def __init__(self, ctx: dict):
        self.ctx = ctx
        self.s: dict = ctx["suspect"]
        self.sid: str = self.s.get("id", "")
        self.state: dict = ctx.get("state") or {}
        self.unlocked: list[str] = list(ctx.get("unlocked") or [])
        self.locked: list[str] = list(
            ctx.get("locked") or [s["id"] for s in self.s.get("secrets", []) if s["id"] not in self.unlocked]
        )
        self.revealed: set[str] = set(self.state.get("revealed_secret_ids") or [])
        self.turn_type: str = ctx.get("turn_type") or "ask"
        self.tactic: str | None = ctx.get("tactic")
        self.evidence: dict | None = ctx.get("evidence")
        self.other: dict | None = ctx.get("confrontation_with")
        self.retry_ids: list[str] = list(ctx.get("retry_ids") or [])
        self.cast_names: dict[str, str] = dict(ctx.get("cast_names") or {})
        self.suspect_ids: list[str] = list(ctx.get("suspect_ids") or self.cast_names.keys())
        self.conversation: list[dict] = list(self.state.get("conversation") or [])
        self.turn_no = ctx.get("turn")
        if self.turn_no is None:
            self.turn_no = len(self.conversation)
        self.raw_message: str = ctx.get("user_message") or ""
        self.message: str = strip_message_prefix(self.raw_message, self.cast_names)
        self.rng = random.Random(stable_seed(self.sid, self.turn_no, self.raw_message))
        self.gender = infer_gender(self.s)
        self.voice = parse_voice(self.s.get("speech_quirk", ""))
        self.personality = self.s.get("personality") or {}
        self.secrets: list[dict] = list(self.s.get("secrets") or [])
        self.by_id = {sec["id"]: sec for sec in self.secrets}
        self.locked_secrets = [sec for sec in self.secrets if sec["id"] in self.locked]
        self.msg_tokens = content_tokens(self.message)
        self.msg_token_set = set(self.msg_tokens)
        # output
        self.spoken = ""
        self.honesty = "evasive"
        self.emotion = "neutral"
        self.stress_delta = 0
        self.reveals: list[str] = []
        self.accuses: str | None = None
        self.wants: list[dict] = []
        self.tell = ""
        self.hidden_secret: dict | None = None  # what the reasoning talks about
        self.plan: str = ""
        self.used_cover: dict | None = None

    # ----------------------------------------------------------------------------------------------------------------
    # helpers
    # ----------------------------------------------------------------------------------------------------------------

    def fp(self, text: str) -> str:
        return first_person(text, self.s, self.cast_names, self.gender)

    def trait(self, name: str, default: float = 0.5) -> float:
        try:
            return float(self.personality.get(name, default))
        except (TypeError, ValueError):
            return default

    def is_unlocked(self, sec: dict) -> bool:
        return sec["id"] in self.unlocked

    def unrevealed_unlocked(self) -> list[dict]:
        return [sec for sec in self.secrets if self.is_unlocked(sec) and sec["id"] not in self.revealed]

    def highest_locked(self) -> dict | None:
        if not self.locked_secrets:
            return None
        return max(self.locked_secrets, key=lambda x: int(x.get("tier", 1)))

    def score_secret(self, sec: dict, tokens: set[str]) -> int:
        sec_tokens = set(content_tokens(sec.get("text", "")))
        sec_tokens |= set(content_tokens(sec.get("cover_story", "")))
        sec_tokens |= {canon(w) for w in regex_words(sec.get("key_phrases", ""))}
        score = sum(2 if t in SYNONYM_GROUPS else 1 for t in tokens & sec_tokens)
        try:
            if sec.get("key_phrases") and re.search(sec["key_phrases"], self.message, re.IGNORECASE):
                score += 2
        except re.error:
            pass
        if self.tactic == "flatter" and int(sec.get("tier", 3)) <= 2:
            score += 1
        return score

    def best_secret(self, tokens: set[str], threshold: int = 2) -> dict | None:
        best: dict | None = None
        best_key: tuple = ()
        for sec in self.secrets:
            sc = self.score_secret(sec, tokens)
            if sc < threshold:
                continue
            key = (sc, 1 if (self.is_unlocked(sec) and sec["id"] not in self.revealed) else 0, -int(sec.get("tier", 3)))
            if best is None or key > best_key:
                best, best_key = sec, key
        return best

    def most_related_locked(self, tokens: set[str]) -> dict | None:
        best, best_sc = None, -1
        for sec in self.locked_secrets:
            sc = self.score_secret(sec, tokens)
            if sc > best_sc:
                best, best_sc = sec, sc
        return best

    def alibi_secret(self) -> dict | None:
        """The secret whose cover story is this suspect's stated alibi (lowest tier with a cover story)."""
        with_cover = [sec for sec in self.secrets if sec.get("cover_story")]
        if not with_cover:
            return None
        return min(with_cover, key=lambda x: int(x.get("tier", 3)))

    def leaks(self, text: str) -> bool:
        for sec in self.locked_secrets:
            pat = sec.get("key_phrases")
            if not pat:
                continue
            try:
                if re.search(pat, text, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    def distinctive_words(self, sec: dict) -> set[str]:
        public = set(content_tokens(self.s.get("public_description", "")))
        for other in self.secrets:
            public |= set(content_tokens(other.get("cover_story", "")))
        names: set[str] = set()
        for name in self.cast_names.values():
            names |= set(content_tokens(name))
        words = {t for t in content_tokens(sec.get("text", "")) if len(t) >= 5 or t in SYNONYM_GROUPS}
        return words - public - names

    def knowledge_is_safe(self, item: str) -> bool:
        rendered = self.fp(item)
        if self.leaks(item) or self.leaks(rendered):
            return False
        toks = set(content_tokens(item))
        for sec in self.locked_secrets:
            if toks & self.distinctive_words(sec):
                return False
        return True

    def best_knowledge(self, tokens: set[str]) -> str | None:
        best, best_sc = None, 0
        for item in self.s.get("knowledge") or []:
            item_tokens = content_tokens(item)
            sc = 0
            for t in set(item_tokens):
                if t in tokens:
                    sc += 2 if (len(t) >= 7 or t in SYNONYM_GROUPS) else 1
            if sc > best_sc and self.knowledge_is_safe(item):
                best, best_sc = item, sc
        return best if best_sc >= 2 else None

    def named_suspect(self, text: str) -> str | None:
        """The first other suspect referred to in text (by name, or by an obvious role word)."""
        best_pos, best_id = None, None
        for oid, name in self.cast_names.items():
            if oid == self.sid:
                continue
            for v in name_variants(name):
                m = re.search(rf"(?<![A-Za-z]){re.escape(v)}(?![A-Za-z])", text)
                if m and (best_pos is None or m.start() < best_pos):
                    best_pos, best_id = m.start(), oid
        if best_id:
            return best_id
        low = text.lower()
        roles = self.ctx.get("cast_roles") or {}
        for oid, name in self.cast_names.items():
            if oid == self.sid:
                continue
            if "ladyship" in low and name.startswith("Lady "):
                return oid
            if re.search(r"\bthe doctor\b", low) and name.startswith("Dr"):
                return oid
            role = str(roles.get(oid, "")).lower()
            if role and re.search(r"\b(housemaid|the maid)\b", low) and "maid" in role:
                return oid
        return None

    def last_assistant_texts(self, n: int = 3) -> list[str]:
        out = [m.get("content", "") for m in self.conversation if m.get("role") == "assistant"]
        return out[-n:]

    def pick_deflection(self, avoid_names: bool = False) -> tuple[str, str, str | None]:
        """A rendered deflection not used in the last reply. Returns (spoken, tell, accuses)."""
        descs = list(self.s.get("deflections") or [])
        recent = " ".join(self.last_assistant_texts(1))
        candidates = []
        for desc in descs:
            spoken, tell = render_deflection(desc, self.s, self.cast_names, self.gender, self.rng)
            if not spoken or self.leaks(spoken):
                continue
            who = self.named_suspect(spoken) or self.named_suspect(desc)
            if avoid_names and who:
                continue
            fresh = spoken[:30] not in recent
            candidates.append((fresh, spoken, tell, who))
        if not candidates:
            generic = self.rng.choice(
                [
                    "I have told you what I know.",
                    "I don't see what that has to do with anything.",
                    "I really couldn't say.",
                    "You would do better to ask someone else about that.",
                ]
            )
            return generic, "", None
        fresh_ones = [c for c in candidates if c[0]] or candidates
        _, spoken, tell, who = self.rng.choice(fresh_ones)
        return spoken, tell, who

    def emotion_for_reveal(self, sec: dict) -> str:
        if int(sec.get("tier", 1)) >= 3:
            return "afraid" if self.trait("nervous") >= 0.5 else "sad"
        if self.trait("nervous") >= 0.6:
            return "afraid"
        if self.trait("proud") >= 0.7:
            return "angry"
        return "sad"

    def emotion_for_locked(self, sec: dict) -> str:
        if int(sec.get("tier", 1)) >= 3:
            return "angry" if self.trait("proud") >= 0.6 else "afraid"
        return "nervous" if self.trait("nervous") >= 0.5 else "neutral"

    def tell_for_emotion(self) -> str:
        tells = self.s.get("tells") or {}
        if self.emotion in ("nervous", "afraid"):
            return tells.get("nervous", "")
        if self.emotion == "angry":
            return tells.get("angry", "")
        if self.emotion == "sad":
            return tells.get("cracking", "")
        return ""

    def trusted_confidant(self) -> str | None:
        rels = self.s.get("relationships") or {}
        best, best_trust = None, -1.0
        for oid, rel in rels.items():
            if oid == self.sid or oid not in self.suspect_ids:
                continue
            if str(rel.get("type", "")).lower() in {"lover", "ally", "trusts"} and float(rel.get("trust", 0)) > best_trust:
                best, best_trust = oid, float(rel.get("trust", 0))
        return best

    def opener(self, kind: str) -> str:
        v, rng = self.voice, self.rng
        sfx = v.suffix()
        if kind == "reveal":
            choices = ["Very well.", "…All right.", "I suppose there is no point pretending.", "If you must know."]
            if v.uses_one:
                choices += ["One supposes there is no point in pretending.", "One had hoped not to say this."]
            if v.formal:
                choices = [f"…Very well{sfx}.", f"If you please{sfx}. I will tell you."]
            if v.warm and v.address:
                choices += [f"{capitalise(v.address)}, {v.address} — all right."]
            if v.medical:
                choices += ["I had hoped to spare everyone this."]
            return rng.choice(choices)
        if kind == "restate":
            return rng.choice(["I have told you this already.", "As I said.", "I will say it once more."])
        if kind == "knowledge":
            choices = ["", "", "Well —", "As far as I know,", "If it helps,"]
            if v.exact:
                choices = ["", "", f"Only this{sfx}:"]
            return rng.choice(choices)
        if kind == "deflect":
            choices = ["I don't see what that has to do with anything.", "I really couldn't say.", "You would have to ask someone else about that.", ""]
            if v.uses_one:
                choices += ["One would rather not.", "One doesn't discuss such things."]
            if v.tics:
                choices += list(v.tics)
            if v.questions:
                choices += ["Why do you ask me that?", "Is that really what you want to know?"]
            if v.medical:
                choices += ["I can only speak to the medical facts."]
            if v.exact:
                choices = [f"I couldn't say{sfx}.", "", f"I don't know about that{sfx}."]
            return rng.choice(choices)
        if kind == "bluff":
            choices = [f"If you had that{sfx}, you would not be asking me.", f"I don't believe you{sfx}.", "That is not true, and I think you know it."]
            if v.questions:
                choices += ["Do you, now? And who told you that?"]
            return rng.choice(choices)
        if kind == "threat":
            choices = ["I will not be spoken to like that.", "You may threaten as you please; my answer is the same.", "That is beneath you."]
            if v.solicitor:
                choices = [f"I think I should like my solicitor present{sfx}.", "Threats, now? My solicitor will be interested to hear it."]
            if v.uses_one:
                choices += ["One is not accustomed to being threatened."]
            if v.formal or v.exact:
                choices += [f"I don't know anything{sfx}."]
            return rng.choice(choices)
        if kind == "silence":
            choices = ["…", "Is there something else?", "Well?", "I don't know what you want me to say."]
            if v.address:
                choices += [f"…{capitalise(v.address)}?"]
            return rng.choice(choices)
        if kind == "flatter":
            choices = ["That's kind of you to say.", "You're very good.", "I'm sure I don't deserve that."]
            if v.uses_one:
                choices += ["One does one's best."]
            if v.warm:
                choices += [f"Ha! You flatter me{sfx}."]
            return rng.choice(choices)
        if kind == "present_self":
            choices = ["I don't know what you expect me to say to that.", "That proves nothing.", "Where did you find that?"]
            if v.questions:
                choices += ["And what do you imagine that shows?"]
            return rng.choice(choices)
        if kind == "present_other":
            return rng.choice(["That has nothing to do with me.", "I've never seen that before.", "You should show that to someone it concerns."])
        return ""

    def add_address(self, text: str) -> str:
        v = self.voice
        if not v.address or not text or self.other:
            return text  # in a confrontation the line is addressed to the other suspect
        if v.address.lower() in text.lower():
            return text
        r = self.rng.random()
        if r < 0.35:
            body = text[0].lower() + text[1:] if text[0].isupper() and not text.startswith("I ") and not text.startswith("I'") else text
            return f"{capitalise(v.address)}, {body}"
        if r < 0.7:
            sents = split_sentences(text)
            if sents:
                first = sents[0]
                if first[-1] in ".!?":
                    sents[0] = first[:-1] + f", {v.address}" + first[-1]
                return " ".join(sents)
        return text

    def apply_one(self, text: str) -> str:
        """Margaret's 'one' for 'I' when uncomfortable (at most one sentence per reply)."""
        if not self.voice.uses_one or self.emotion not in ("nervous", "afraid", "angry"):
            return text
        safe = {
            "was": "was", "went": "went", "did": "did", "had": "had", "heard": "heard", "saw": "saw", "came": "came",
            "could": "could", "would": "would", "should": "should", "will": "will", "can": "can", "cannot": "cannot",
            "must": "must", "might": "might", "don't": "doesn't", "didn't": "didn't", "wasn't": "wasn't",
            "have": "has", "am": "is",
        }
        sents = split_sentences(text)
        pat = re.compile(r"^I (\w+(?:'t)?)\b(.*)$")
        eligible = [i for i, sent in enumerate(sents) if (m := pat.match(sent)) and m.group(1) in safe]
        if not eligible or self.rng.random() > 0.7:
            return text
        i = self.rng.choice(eligible)
        m = pat.match(sents[i])
        sents[i] = f"One {safe[m.group(1)]}{m.group(2)}"
        return " ".join(sents)

    # ----------------------------------------------------------------------------------------------------------------
    # composition primitives
    # ----------------------------------------------------------------------------------------------------------------

    def reveal(self, sec: dict, *, prefix: str | None = None) -> None:
        opener = self.opener("reveal") if prefix is None else prefix
        budget = MAX_SENTENCES - count_sentences(opener)
        body = limit_sentences(self.fp(sec.get("text", "")), max(1, budget))
        self.spoken = f"{opener} {body}".strip()
        self.honesty = "truthful"
        self.reveals = [sec["id"]]
        self.stress_delta = 1
        self.emotion = self.emotion_for_reveal(sec)
        label = secret_label(sec, self.s, self.cast_names, self.gender)
        self.hidden_secret = None
        self.plan = f"They already had me on {label}; better it comes from me than from someone else."
        confidant = self.trusted_confidant()
        if confidant:
            self.wants = [{"to": confidant, "message": f"The detective asked me about {label}. Be careful."}]

    def restate(self, sec: dict) -> None:
        body = split_sentences(self.fp(sec.get("text", "")))
        first = body[0] if body else ""
        self.spoken = f"{self.opener('restate')} {first}".strip()
        self.honesty = "truthful"
        self.stress_delta = 0
        self.emotion = "neutral" if self.trait("nervous") < 0.6 else "nervous"
        self.plan = "I have already admitted that much; repeating it costs me nothing."

    def cover(self, sec: dict, *, prefix: str = "") -> None:
        body = self.fp(sec.get("cover_story", ""))
        self.spoken = f"{prefix} {body}".strip()
        self.honesty = "lie"
        self.emotion = self.emotion_for_locked(sec)
        self.stress_delta = 2 if int(sec.get("tier", 1)) >= 3 else 1
        self.hidden_secret = sec
        self.used_cover = sec
        self.plan = "the story will have to hold"

    def deflect(self, *, prefix: str = "", avoid_names: bool = False, force_accuse: str | None = None) -> None:
        spoken, tell, who = self.pick_deflection(avoid_names=avoid_names)
        self.spoken = f"{prefix} {spoken}".strip()
        self.honesty = "evasive"
        if tell and not self.tell:
            self.tell = tell
        who = force_accuse or who
        if who and who in self.suspect_ids and who != self.sid:
            self.accuses = who
        if self.hidden_secret is None:
            self.hidden_secret = self.highest_locked()
        self.plan = f"I'll point them at {self.cast_names.get(self.accuses, self.accuses)}" if self.accuses else "I'll give them nothing"

    def answer_knowledge(self, item: str, *, prefix: str | None = None) -> None:
        opener = self.opener("knowledge") if prefix is None else prefix
        budget = MAX_SENTENCES - count_sentences(opener)
        body = limit_sentences(self.fp(item), max(1, budget))
        self.spoken = f"{opener} {body}".strip()
        self.honesty = "truthful"
        self.emotion = "neutral"
        self.stress_delta = 0
        who = self.named_suspect(item)
        if who and who != self.sid and _SUSPICION_RE.search(item):
            self.accuses = who  # the fact points a finger, not merely mentions a name
        self.plan = "that much is safe to tell"

    # ----------------------------------------------------------------------------------------------------------------
    # the decision tree
    # ----------------------------------------------------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        if self.retry_ids:
            self.handle_retry()
        elif self.other:
            self.handle_confrontation()
        elif self.turn_type == "present" and self.evidence:
            self.handle_present()
        elif self.turn_type == "tactic" and self.tactic:
            self.handle_tactic()
        else:
            self.handle_ask()
        return self.finish()

    def handle_retry(self) -> None:
        for rid in self.retry_ids:
            if rid in self.by_id:
                self.hidden_secret = self.by_id[rid]
        self.emotion = "nervous"
        self.deflect(prefix=self.rng.choice(["", "I have said too much already.", "Forget what I said."]))
        self.stress_delta = 1
        self.plan = "I nearly gave it away; say nothing more about it"

    def handle_ask(self) -> None:
        topic = self.best_secret(self.msg_token_set)
        if topic is None and WHEREABOUTS_RE.search(self.message):
            topic = self.alibi_secret()
        if topic is not None:
            self.answer_on_topic(topic)
            return
        item = self.best_knowledge(self.msg_token_set)
        if item:
            self.answer_knowledge(item)
            return
        smug = self.trait("proud") >= 0.7 and self.trait("nervous") <= 0.3 and self.rng.random() < 0.5
        self.emotion = "smug" if smug else "neutral"
        self.deflect(prefix=self.opener("deflect"))

    def answer_on_topic(self, sec: dict) -> None:
        if self.is_unlocked(sec):
            if sec["id"] in self.revealed:
                self.restate(sec)
            else:
                self.reveal(sec)
            return
        if sec.get("cover_story"):
            self.cover(sec)
        else:
            self.emotion = self.emotion_for_locked(sec)
            self.hidden_secret = sec
            self.deflect(prefix=self.opener("deflect"))
            self.stress_delta = 2 if int(sec.get("tier", 1)) >= 3 else 1

    def handle_present(self) -> None:
        ev = self.evidence or {}
        ev_tokens = set(content_tokens(f"{ev.get('name', '')} {ev.get('text', '')}"))
        topic = self.best_secret(ev_tokens, threshold=1)
        if ev.get("points_to_self"):
            if topic is not None and self.is_unlocked(topic) and topic["id"] not in self.revealed:
                self.reveal(topic, prefix=self.opener("present_self"))
                self.stress_delta = 2
                # pivot: point at someone else if the sentence budget allows
                budget = MAX_SENTENCES - count_sentences(self.spoken)
                if budget >= 1:
                    spoken, _tell, who = self.pick_deflection()
                    if who and who != self.sid:
                        self.spoken = f"{self.spoken} {limit_sentences(spoken, budget)}"
                        self.accuses = who
                return
            related = self.most_related_locked(ev_tokens) if self.locked_secrets else None
            if related is not None and related.get("cover_story"):
                self.cover(related, prefix=self.opener("present_self"))
            else:
                if related is not None:
                    self.hidden_secret = related
                self.emotion = "afraid" if self.trait("nervous") >= 0.5 else "nervous"
                self.deflect(prefix=self.opener("present_self"))
            self.stress_delta = 2
            if self.emotion == "neutral":
                self.emotion = "nervous"
            return
        # points elsewhere: calm, redirect
        self.emotion = "neutral"
        self.stress_delta = 0
        if topic is not None and self.is_unlocked(topic) and topic["id"] not in self.revealed:
            self.reveal(topic, prefix=self.opener("present_other"))
            return
        self.deflect(prefix=self.opener("present_other"))
        who = self.named_suspect(ev.get("text", ""))
        if who and who != self.sid and not self.accuses:
            self.accuses = who
        self.honesty = "evasive"

    def handle_tactic(self) -> None:
        t = self.tactic
        if t == "flatter":
            sensitivity = int((self.s.get("stress_sensitivity") or {}).get("flatter", 1))
            topic = self.best_secret(self.msg_token_set)
            if topic is not None and self.is_unlocked(topic) and topic["id"] not in self.revealed:
                self.reveal(topic, prefix=self.opener("flatter"))
                return
            pending = self.unrevealed_unlocked()
            if pending and sensitivity >= 2:
                sec = max(pending, key=lambda x: int(x.get("tier", 1)))
                self.reveal(sec, prefix=self.opener("flatter"))
                self.stress_delta = 0
                return
            if topic is not None:
                self.answer_on_topic(topic)
                self.spoken = f"{self.opener('flatter')} {self.spoken}"
                return
            item = self.best_knowledge(self.msg_token_set)
            if item:
                self.answer_knowledge(item, prefix=self.opener("flatter"))
                return
            self.emotion = "smug" if self.trait("proud") >= 0.7 else "neutral"
            self.deflect(prefix=self.opener("flatter"))
            self.stress_delta = 0
            return
        if t == "threaten":
            self.emotion = "angry" if self.trait("proud") >= 0.4 else "afraid"
            topic = self.best_secret(self.msg_token_set)
            if topic is not None and self.is_unlocked(topic) and topic["id"] not in self.revealed:
                self.reveal(topic, prefix=self.opener("threat"))
                self.stress_delta = 2
                self.emotion = "afraid"
                return
            if topic is not None:
                self.hidden_secret = topic
            self.deflect(prefix=self.opener("threat"))
            self.stress_delta = 2
            return
        if t == "bluff":
            topic = self.best_secret(self.msg_token_set)
            if topic is not None and self.is_unlocked(topic) and topic["id"] not in self.revealed:
                self.reveal(topic, prefix=self.rng.choice(["…So you know.", "I see there is no point denying it."]))
                self.stress_delta = 2
                return
            self.emotion = "nervous" if self.trait("nervous") >= 0.6 else ("smug" if self.trait("proud") >= 0.7 else "neutral")
            if topic is not None:
                self.hidden_secret = topic
                if topic.get("cover_story") and self.rng.random() < 0.5:
                    self.cover(topic, prefix=self.opener("bluff"))
                    self.stress_delta = 1
                    return
            self.deflect(prefix=self.opener("bluff"))
            self.stress_delta = 1 if self.emotion == "nervous" else 0
            self.plan = "they are bluffing; hold the line"
            return
        if t == "silence":
            pending = self.unrevealed_unlocked()
            self.emotion = "nervous"
            if pending:
                sec = max(pending, key=lambda x: int(x.get("tier", 1)))
                self.reveal(sec, prefix=self.opener("silence"))
                self.emotion = self.emotion_for_reveal(sec)
                return
            self.deflect(prefix=self.opener("silence"), avoid_names=self.rng.random() < 0.5)
            self.stress_delta = 1
            return
        # unknown tactic: behave like an ask
        self.handle_ask()

    def handle_confrontation(self) -> None:
        other = self.other or {}
        oid = other.get("id")
        oname = other.get("name") or self.cast_names.get(oid, oid or "")
        rel = (self.s.get("relationships") or {}).get(oid, {}) if oid else {}
        rel_type = str(rel.get("type", "")).lower()
        addr = other_address(oname, rel_type, self.voice)
        if self.leaks(addr):  # e.g. a first name that the case treats as a give-away
            addr = other_address(oname, "acquaintance", self.voice)
        warm = rel_type in {"lover", "ally", "trusts"}
        hostile = rel_type in {"dislikes", "leverage", "threatens", "rival", "enemy"}
        guilty = bool(self.s.get("guilty"))
        topic = self.best_secret(self.msg_token_set)
        if topic is None and WHEREABOUTS_RE.search(self.message):
            topic = self.alibi_secret()
        # an unlocked, unrevealed secret raised in the room comes out (addressed to the other suspect)
        if topic is not None and self.is_unlocked(topic) and topic["id"] not in self.revealed:
            op = self.opener("reveal")
            self.reveal(topic, prefix=f"{addr}, {op[0].lower() + op[1:] if op and op[0].isalpha() else op}")
            if warm and oid:
                label = secret_label(topic, self.s, self.cast_names, self.gender)
                self.wants = [{"to": oid, "message": f"I had to tell them about {label}. I'm sorry."}]
            return
        if warm and not (guilty and hostile):
            alibi = self.alibi_secret()
            align = self.rng.choice(
                [
                    f"{addr}, we have both told the detective what happened.",
                    f"{addr}, there is nothing more to say than what we have already said.",
                    f"We were exactly where we said we were, {addr}.",
                ]
            )
            if alibi is not None and alibi["id"] in self.locked:
                self.cover(alibi, prefix=align)
                self.emotion = "nervous" if self.trait("nervous") >= 0.5 else "neutral"
            else:
                self.spoken = align
                self.honesty = "evasive"
                self.emotion = "neutral"
                self.stress_delta = 0
                self.hidden_secret = self.highest_locked()
            self.plan = f"keep {addr} steady; we tell the same story"
            self.stress_delta = max(self.stress_delta, 1)
            return
        if hostile or guilty:
            if topic is not None and not self.is_unlocked(topic) and topic.get("cover_story") and self.rng.random() < 0.4:
                self.cover(topic, prefix=self.rng.choice([f"{addr}, you know perfectly well where I was.", f"Say what you like, {addr}."]))
                self.accuses = oid
                return
            lead = self.rng.choice(
                [
                    f"{addr}, why don't you tell the detective where you really were?",
                    f"Perhaps {addr} would like to explain the evening properly.",
                    f"I think {addr} has rather more to account for than I have.",
                ]
            )
            self.emotion = "angry" if self.trait("proud") >= 0.6 else "nervous"
            if topic is not None and not self.is_unlocked(topic):
                self.hidden_secret = topic
            if self.rng.random() < 0.5:
                self.deflect(prefix=lead, force_accuse=oid)
            else:
                self.spoken = lead
                self.honesty = "evasive"
                if self.hidden_secret is None:
                    self.hidden_secret = self.highest_locked()
            self.accuses = oid
            self.stress_delta = 1
            return
        if rel_type == "fears":
            self.emotion = "afraid"
            self.hidden_secret = self.highest_locked()
            if topic is not None and topic.get("cover_story") and not self.is_unlocked(topic):
                self.cover(topic, prefix=self.rng.choice(["I— yes.", "…"]))
            else:
                self.deflect(prefix=self.rng.choice([f"I don't want any trouble, {addr}.", "I only bring the coffee.", ""]), avoid_names=True)
            self.stress_delta = 2
            return
        # neutral relationship (employer, acquaintance, kind_to): answer as in an ask, addressing them
        if topic is not None:
            self.answer_on_topic(topic)
        else:
            item = self.best_knowledge(self.msg_token_set)
            if item:
                self.answer_knowledge(item)
            else:
                self.deflect()
        if self.spoken and not self.spoken.startswith(addr):
            lower_ok = self.spoken[0].isupper() and not self.spoken.startswith(("I ", "I'"))
            self.spoken = f"{addr}, {self.spoken[0].lower() + self.spoken[1:] if lower_ok else self.spoken}"

    # ----------------------------------------------------------------------------------------------------------------
    # finishing
    # ----------------------------------------------------------------------------------------------------------------

    def reasoning(self) -> str:
        who = self.cast_names.get(self.accuses, self.accuses) if self.accuses else None
        if self.reveals:
            return self.plan or "Better they hear it from me."
        if self.hidden_secret is not None:
            label = secret_label(self.hidden_secret, self.s, self.cast_names, self.gender)
            if self.used_cover is not None:
                return f"I must keep them away from {label}; the story I told about {self.cover_snippet(self.used_cover)} has to hold."
            if who:
                return f"I must not let them near {label}; I'll point them at {who}."
            return f"I must not let them near {label}; {self.plan or 'I will give them nothing'}."
        top = self.highest_locked()
        if top is not None:
            label = secret_label(top, self.s, self.cast_names, self.gender)
            if self.honesty == "truthful":
                return f"That much is safe to tell; {label} is not."
            return f"Say nothing that leads to {label}; {self.plan or 'give them nothing'}."
        return "I have nothing left to hide; I only want this over."

    def cover_snippet(self, sec: dict) -> str:
        label = topic_label(sec.get("cover_story", ""), "", self.cast_names)
        if label:
            return label
        words = self.fp(sec.get("cover_story", "")).split()
        return " ".join(words[:5]).rstrip(".,;") + ("…" if len(words) > 5 else "")

    def finish(self) -> dict[str, Any]:
        spoken = capitalise(ensure_terminal(self.spoken))
        spoken = self.add_address(spoken)
        spoken = self.apply_one(spoken)
        spoken = limit_sentences(spoken, MAX_SENTENCES)
        # rule 9: regex leak check against locked secrets; replace on a hit
        attempts = 0
        while self.leaks(spoken) and attempts < 6:
            attempts += 1
            log.info("scripted %s: self-check caught a locked phrase; replacing line", self.sid)
            self.reveals = []
            self.honesty = "evasive"
            alt, tell, who = self.pick_deflection(avoid_names=attempts > 3)
            spoken = limit_sentences(capitalise(ensure_terminal(alt)), MAX_SENTENCES)
            if who and who in self.suspect_ids and who != self.sid:
                self.accuses = who
        if self.leaks(spoken) or not spoken.strip():
            spoken = "I have told you everything I intend to."
            self.honesty = "evasive"
        self.reveals = [r for r in self.reveals if r in self.unlocked]
        if self.accuses is not None and (self.accuses not in self.suspect_ids or self.accuses == self.sid):
            self.accuses = None
        self.wants = [w for w in self.wants if w.get("to") in self.suspect_ids and w.get("to") != self.sid]
        if self.emotion not in ("neutral", "nervous", "angry", "smug", "sad", "afraid"):
            self.emotion = "neutral"
        if self.honesty not in ("truthful", "evasive", "lie"):
            self.honesty = "evasive"
        tell = self.tell or self.tell_for_emotion()
        return {
            "spoken": spoken,
            "internal_reasoning": self.reasoning(),
            "honesty": self.honesty,
            "emotion": self.emotion,
            "stress_delta": max(-2, min(3, int(self.stress_delta))),
            "reveals": list(dict.fromkeys(self.reveals)),
            "accuses": self.accuses,
            "wants_to_tell": self.wants,
            "tell": tell,
        }
