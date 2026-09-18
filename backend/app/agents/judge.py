"""Small judging helpers (PLAN §7.4, §8.9): motive grading, fallback lines, conversation summaries.

Each has a scripted (pure-code) implementation and a Gemini implementation that falls back to the scripted one.
"""

from __future__ import annotations

import logging
import re

from . import client as llm
from .scripted import STOPWORDS, ensure_terminal, parse_voice, split_sentences, stem
from .tools import FALLBACK_LINES, GRADE_MOTIVE, SUMMARIZE

log = logging.getLogger("alibi.agents.judge")

_NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "twenty",
    "thirty", "forty", "fifty", "hundred", "thousand", "million", "first", "second", "third", "half", "quarter",
    "about", "roughly", "nearly",
}
_GENERIC = {"intend", "intent", "mean", "meant", "would", "going", "about", "sir", "lady", "mister", "thing", "murder", "kill", "killed", "victim"}
_BIGRAMS = {
    "found out": "discover",
    "find out": "discover",
    "go to the police": "police",
    "went to the police": "police",
    "end the partnership": "dissolve",
    "break up the partnership": "dissolve",
    "cook the books": "embezzle",
    "cooked the books": "embezzle",
    "took money": "embezzle",
    "taking money": "embezzle",
    "stealing money": "embezzle",
    "cover up": "conceal",
    "covered up": "conceal",
}
# stem prefix -> concept (motive vocabulary that players paraphrase most)
_ALIASES = [
    ("embezzl", "embezzle"), ("steal", "embezzle"), ("stole", "embezzle"), ("theft", "embezzle"), ("thief", "embezzle"),
    ("skim", "embezzle"), ("fraud", "embezzle"), ("swindl", "embezzle"), ("defraud", "embezzle"), ("pilfer", "embezzle"),
    ("discov", "discover"), ("knew", "discover"), ("know", "discover"), ("learn", "discover"), ("expos", "discover"),
    ("caught", "discover"), ("uncover", "discover"), ("realis", "discover"), ("realiz", "discover"),
    ("polic", "police"), ("prosecut", "police"), ("arrest", "police"), ("prison", "police"), ("jail", "police"),
    ("dissol", "dissolve"), ("partner", "partnership"), ("firm", "partnership"), ("busines", "partnership"),
    ("account", "accounts"), ("ledger", "accounts"), ("book", "accounts"), ("pound", "money"), ("cash", "money"),
    ("fund", "money"), ("debt", "money"), ("inherit", "inheritance"), ("will", "inheritance"), ("legacy", "inheritance"),
    ("estate", "inheritance"), ("fortun", "inheritance"), ("affair", "affair"), ("lover", "affair"), ("mistress", "affair"),
    ("jealous", "jealousy"), ("revenge", "revenge"), ("aveng", "revenge"), ("blackmail", "blackmail"), ("silenc", "silence"),
    ("secret", "secret"), ("scandal", "scandal"), ("ruin", "ruin"), ("disgrac", "ruin"), ("shame", "ruin"),
]


def _concept(word: str) -> str | None:
    lw = word.lower()
    if lw in STOPWORDS or lw in _NUMBER_WORDS or len(lw) < 4:
        return None
    st = stem(lw)
    if st in _GENERIC or lw in _GENERIC:
        return None
    for prefix, concept in _ALIASES:
        if st.startswith(prefix) or lw.startswith(prefix):
            return concept
    return st if len(st) >= 4 else None


def motive_concepts(text: str) -> set[str]:
    """Canonical concept set for a motive sentence (aliases, bigrams, no numbers or generic words)."""
    low = (text or "").lower()
    concepts: set[str] = set()
    for phrase, concept in _BIGRAMS.items():
        if phrase in low:
            concepts.add(concept)
    for word in re.findall(r"[A-Za-z][A-Za-z'\-]+", text or ""):
        c = _concept(word.strip("'-"))
        if c:
            concepts.add(c)
    return concepts


def grade_motive_scripted(motive_text: str, solution_motive: str) -> dict:
    solution = motive_concepts(solution_motive)
    player = motive_concepts(motive_text)
    if not solution:
        return {"points": 0, "note": "No motive to compare against."}
    overlap = solution & player
    ratio = len(overlap) / len(solution)
    if ratio >= 0.5:
        points = 20
        note = "Your motive matches the truth in its essentials."
    elif ratio >= 0.25:
        points = 10
        note = "You had part of the motive; the full reason was more specific."
    else:
        points = 0
        note = "Your motive did not match what really drove the murderer."
    if overlap:
        pretty = ", ".join(sorted(o.replace("the ", "") for o in overlap))
        note += f" (You touched on: {pretty}.)"
    return {"points": points, "note": note}


async def grade_motive(motive_text: str, solution_motive: str, mode: str = "scripted") -> dict:
    """{"points": 0|10|20, "note": str}."""
    if mode == "gemini":
        system = (
            "You grade a detective's stated motive against the true motive of a murder mystery. Award 20 points if the "
            "detective's motive is essentially right (same underlying reason, even if worded differently), 10 if it is "
            "partly right or on the right track, 0 if it is wrong or too vague to count. Write one short note for the "
            "debrief, addressed to the detective, without revealing anything beyond the true motive."
        )
        user = f"True motive: {solution_motive}\n\nDetective's stated motive: {motive_text or '(nothing)'}"
        try:
            raw = await llm.call_tool("guard", system, [{"role": "user", "content": user}], GRADE_MOTIVE, max_tokens=1200, temperature=0.0)
            points = int(raw.get("points", 0))
            if points not in (0, 10, 20):
                points = 20 if points >= 15 else (10 if points >= 5 else 0)
            return {"points": points, "note": str(raw.get("note") or "")}
        except (llm.LLMUnavailable, llm.InvalidOutput, llm.NotConfigured, ValueError, TypeError) as exc:
            log.warning("grade_motive model unavailable (%s); using scripted grader", exc)
    return grade_motive_scripted(motive_text, solution_motive)


def fallback_line_for(suspect: dict) -> str:
    """One in-character 'I've said all I'm going to say' line from the speech_quirk."""
    v = parse_voice(suspect.get("speech_quirk", ""))
    addr = v.address
    if v.uses_one:
        return "One has said all one intends to say."
    if v.solicitor:
        return f"I've said all I'm going to say{', ' + addr if addr else ''}. Anything further can go through my solicitor."
    if v.formal and addr in ("sir", "madam", "ma'am"):
        return f"I've said all I know, {addr}. If you please, I'd like to get back to my work."
    if v.medical or v.questions:
        return f"I have said all I am going to say{', ' + addr if addr else ''}. Is there anything else?"
    if addr:
        return f"I've said all I'm going to say, {addr}."
    return "I've said all I'm going to say."


def fallback_lines_scripted(case: dict) -> dict[str, str]:
    return {s["id"]: fallback_line_for(s) for s in case.get("suspects", []) if s.get("id")}


async def fallback_lines(case: dict, mode: str = "scripted") -> dict[str, str]:
    """{suspect_id: line} — generated once at game start."""
    scripted = fallback_lines_scripted(case)
    if mode != "gemini":
        return scripted
    cast = [
        {"suspect_id": s["id"], "name": s.get("name", ""), "role": s.get("role", ""), "speech_quirk": s.get("speech_quirk", "")}
        for s in case.get("suspects", [])
        if s.get("id")
    ]
    system = (
        "For each character below, write ONE line of dialogue (1-2 sentences) in which they tell a detective, in their "
        "own voice, that they have said all they are going to say. Match the speech quirk exactly. Do not invent facts."
    )
    user = "\n".join(f"- {c['suspect_id']}: {c['name']}, {c['role']}. How they speak: {c['speech_quirk']}" for c in cast)
    try:
        raw = await llm.call_tool("guard", system, [{"role": "user", "content": user}], FALLBACK_LINES, max_tokens=1200, temperature=0.8)
        out = dict(scripted)
        for item in raw.get("lines") or []:
            sid = str(item.get("suspect_id", ""))
            line = str(item.get("line") or "").strip()
            if sid in out and line:
                out[sid] = ensure_terminal(line)
        return out
    except (llm.LLMUnavailable, llm.InvalidOutput, llm.NotConfigured) as exc:
        log.warning("fallback_lines model unavailable (%s); using scripted lines", exc)
        return scripted


def summarize_scripted(messages: list[dict], max_chars: int = 900) -> str:
    """Extractive summary: the first sentence of each message, oldest first, capped."""
    parts: list[str] = []
    for m in messages or []:
        content = str(m.get("content", "")).strip()
        if not content:
            continue
        role = m.get("role", "user")
        first = split_sentences(content)
        snippet = (first[0] if first else content)[:140].strip()
        if role == "assistant":
            parts.append(f'I said: "{snippet}"')
        else:
            snippet = re.sub(r"^Detective(?: \([a-z]+\))?:\s*", "", snippet, flags=re.IGNORECASE)
            parts.append(f'The detective said: "{snippet}"')
    text = " ".join(parts)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text or "Nothing of note was said."


async def summarize(messages: list[dict], mode: str = "scripted") -> str:
    """A few-sentence summary of the earlier part of an interrogation (PLAN §7.2)."""
    if mode == "gemini" and messages:
        system = (
            "Summarise the earlier part of this interrogation in 3-6 sentences from the interviewee's point of view "
            "('The detective asked me about ...; I said ...'). Keep every concrete claim, admission and denial. "
            "Do not add anything that was not said."
        )
        transcript = "\n".join(
            f"{'ME' if m.get('role') == 'assistant' else 'DETECTIVE'}: {str(m.get('content', '')).strip()}" for m in messages
        )
        try:
            raw = await llm.call_tool("guard", system, [{"role": "user", "content": transcript}], SUMMARIZE, max_tokens=1200, temperature=0.2)
            summary = str(raw.get("summary") or "").strip()
            if summary:
                return summary
        except (llm.LLMUnavailable, llm.InvalidOutput, llm.NotConfigured) as exc:
            log.warning("summarize model unavailable (%s); using extractive summary", exc)
    return summarize_scripted(messages)
