"""Watson — the detective's notebook (PLAN §7.5).

``update(visible, mode)`` -> NotebookEntry ``{per_suspect, contradictions, suggested_next, turn}``.

The input is *player-visible only* (turns with detective text and spoken lines, examined evidence, the public
timeline, the cast, the locations).  Never internal reasoning, secrets, stress, heard_log or points_to.

Scripted mode is a rule-based extractor; Gemini mode asks the SUSPECT_MODEL with the same input and falls back to
the rule-based notebook when the call fails.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from . import client as llm
from .scripted import name_variants, split_name, split_sentences
from .tools import NOTEBOOK_UPDATE

log = logging.getLogger("alibi.agents.watson")

# --------------------------------------------------------------------------------------------------------------------
# Time phrases
# --------------------------------------------------------------------------------------------------------------------

_HOURS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "midnight": 0, "noon": 12, "midday": 12,
}
_MINUTES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "twenty-one": 21, "twenty one": 21, "twenty-two": 22, "twenty two": 22,
    "twenty-three": 23, "twenty three": 23, "twenty-four": 24, "twenty four": 24, "twenty-five": 25, "twenty five": 25,
    "twenty-six": 26, "twenty six": 26, "twenty-seven": 27, "twenty seven": 27, "twenty-eight": 28, "twenty eight": 28,
    "twenty-nine": 29, "twenty nine": 29, "thirty": 30, "quarter": 15, "a quarter": 15, "half": 30,
}
_HOUR_ALT = "|".join(sorted(_HOURS, key=len, reverse=True))
_MIN_ALT = "|".join(re.escape(m) for m in sorted(_MINUTES, key=len, reverse=True))
_TIME_PATTERNS = [
    ("numeric", re.compile(r"\b(\d{1,2})[:.](\d{2})\b")),
    ("past", re.compile(rf"\b({_MIN_ALT})(?: minutes?)? (?:past|after) ({_HOUR_ALT})\b", re.IGNORECASE)),
    ("to", re.compile(rf"\b({_MIN_ALT})(?: minutes?)? (?:to|before|till) ({_HOUR_ALT})\b", re.IGNORECASE)),
    ("oclock", re.compile(rf"\b({_HOUR_ALT}) o'?clock\b", re.IGNORECASE)),
    ("bare", re.compile(rf"\b(?:at|about|around|until|till|before|after|from|by|past|since|near|nearly|just after|just before|towards|toward)\s+(?:about\s+|nearly\s+|almost\s+|around\s+)?({_HOUR_ALT})\b(?!\s+(?:minutes?|o'clock|past|to|guests?|people|men|years?|pounds?|days?|cigars?|glasses?|of))", re.IGNORECASE)),
    ("midnight", re.compile(r"\b(midnight)\b", re.IGNORECASE)),
]


def _hhmm(hh: int, mm: int) -> str:
    return f"{hh % 24:02d}:{mm % 60:02d}"


def _adjust_pm(hh: int, pm: bool) -> int:
    """Night-time cases: 'eleven' means 23:00 and 'one' means 01:00."""
    if not pm:
        return hh
    if 6 <= hh <= 11:
        return hh + 12
    if hh == 12:
        return 0  # 'twelve' at night is midnight ('quarter to twelve' -> 23:45 via the -1 below)
    return hh


def parse_times(sentence: str, pm: bool = True) -> list[tuple[int, str]]:
    """[(position, 'HH:MM'), ...] for every time phrase in the sentence, in order."""
    found: dict[int, str] = {}
    spans: list[tuple[int, int]] = []
    for kind, pat in _TIME_PATTERNS:
        for m in pat.finditer(sentence):
            start, end = m.start(), m.end()
            if any(start < b and a < end for a, b in spans):
                continue  # already covered by a more specific phrase ('half past ten' beats 'past ten')
            try:
                if kind == "numeric":
                    hh, mm = int(m.group(1)), int(m.group(2))
                    if hh > 23 or mm > 59:
                        continue
                    hh = _adjust_pm(hh, pm) if hh <= 12 else hh
                elif kind == "past":
                    mm = _MINUTES[m.group(1).lower()]
                    hh = _adjust_pm(_HOURS[m.group(2).lower()], pm)
                elif kind == "to":
                    mm = 60 - _MINUTES[m.group(1).lower()]
                    hh = _adjust_pm(_HOURS[m.group(2).lower()], pm) - 1
                elif kind == "oclock" or kind == "bare":
                    hh, mm = _adjust_pm(_HOURS[m.group(1).lower()], pm), 0
                else:  # midnight
                    hh, mm = 0, 0
            except (KeyError, ValueError):
                continue
            found[start] = _hhmm(hh, mm)
            spans.append((start, end))
    return sorted(found.items())


def _minutes(hhmm: str) -> int | None:
    m = re.match(r"^(\d{2}):(\d{2})$", hhmm or "")
    if not m:
        return None
    total = int(m.group(1)) * 60 + int(m.group(2))
    if total < 6 * 60:  # after midnight sorts after the evening
        total += 24 * 60
    return total


# --------------------------------------------------------------------------------------------------------------------
# Location phrases
# --------------------------------------------------------------------------------------------------------------------

_GENERIC_LOCATIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:in|to|into|on|out to|out in|down to|from|across|through) the (?:garden|terrace|grounds)\b|\bgarden (?:bench|door|gate)\b|\bon the bench\b|\bunder the yew\b", re.IGNORECASE), "garden"),
    (re.compile(r"\b(?:to|in|into|up to|from) (?:my|her|his) (?:own )?room\b", re.IGNORECASE), "my room"),
    (re.compile(r"\bthe study\b", re.IGNORECASE), "study"),
    (re.compile(r"\bthe kitchen\b|\bthe scullery\b", re.IGNORECASE), "kitchen"),
    (re.compile(r"\bthe billiard(?:s)? room\b", re.IGNORECASE), "billiard room"),
    (re.compile(r"\bupstairs\b|\bin bed\b|\bto bed\b|\bwent up to bed\b|\bmy bedroom\b|\bretired for the night\b", re.IGNORECASE), "upstairs"),
    (re.compile(r"\bthe servants['’]? corridor\b|\bthe (?:back )?corridor\b|\boutside the study\b|\bby the study door\b|\bthe passage\b", re.IGNORECASE), "servants' corridor"),
    (re.compile(r"\bthe darkroom\b|\bthe dark room\b", re.IGNORECASE), "darkroom"),
    (re.compile(r"\bthe drawing[- ]room\b", re.IGNORECASE), "drawing room"),
    (re.compile(r"\bthe dining[- ]room\b", re.IGNORECASE), "dining room"),
    (re.compile(r"\bthe library\b", re.IGNORECASE), "library"),
    (re.compile(r"\bthe (?:front |entrance )?hall\b", re.IGNORECASE), "hall"),
    (re.compile(r"\bthe cellar\b|\bthe wine cellar\b", re.IGNORECASE), "cellar"),
    (re.compile(r"\bthe stables?\b", re.IGNORECASE), "stables"),
    (re.compile(r"\bthe conservatory\b", re.IGNORECASE), "conservatory"),
    (re.compile(r"\bthe (?:upper |lower |promenade )?deck\b", re.IGNORECASE), "deck"),
    (re.compile(r"\bthe cabin\b|\bmy cabin\b", re.IGNORECASE), "cabin"),
    (re.compile(r"\bthe office\b|\bmy office\b|\bmy desk\b", re.IGNORECASE), "office"),
    (re.compile(r"\bthe lounge\b|\bthe common room\b", re.IGNORECASE), "lounge"),
    (re.compile(r"\bthe chapel\b", re.IGNORECASE), "chapel"),
    (re.compile(r"\bthe bathroom\b|\bthe lavatory\b", re.IGNORECASE), "lavatory"),
    (re.compile(r"\b(?:on the |the )telephone\b|\btelephoning\b|\bphoned\b|\bon the line\b|\bmaking a call\b", re.IGNORECASE), "telephone"),
]
_NEGATION_RE = re.compile(r"\b(?:not|never|didn't|did not|wasn't|was not|weren't|nowhere near|nobody|no one)\b(?:\s+\S+){0,4}\s*$", re.IGNORECASE)
_WHOLE_EVENING_RE = re.compile(r"\b(?:all|the whole|the entire|every minute of the) (?:evening|night)\b|\ball night long\b", re.IGNORECASE)
_SAW_RE = re.compile(r"\b(?:saw|seen|see|watched|noticed|spotted|caught sight of|observed|passed|met|found|came across|heard)\b", re.IGNORECASE)


def _location_patterns(locations: list[dict]) -> list[tuple[re.Pattern, str]]:
    pats: list[tuple[re.Pattern, str]] = []
    for loc in locations or []:
        name = str(loc.get("name") or "").strip()
        if not name:
            continue
        label = re.sub(r"^the\s+", "", name, flags=re.IGNORECASE).lower()
        pats.append((re.compile(rf"\b(?:the\s+)?{re.escape(label)}\b", re.IGNORECASE), label))
    return pats + _GENERIC_LOCATIONS


def find_location(sentence: str, pats: list[tuple[re.Pattern, str]]) -> tuple[str, int] | None:
    """(label, position) of the leftmost location phrase, ignoring negated ones ('did not go near the study')."""
    best: tuple[str, int] | None = None
    for pat, label in pats:
        m = pat.search(sentence)
        if not m:
            continue
        if _NEGATION_RE.search(sentence[: m.start()]):
            continue
        if best is None or m.start() < best[1]:
            best = (label, m.start())
    return best


# --------------------------------------------------------------------------------------------------------------------
# Cast references
# --------------------------------------------------------------------------------------------------------------------


def _cast_matchers(cast: list[dict]) -> dict[str, list[re.Pattern]]:
    out: dict[str, list[re.Pattern]] = {}
    for member in cast or []:
        sid = member.get("id")
        if not sid:
            continue
        pats = [re.compile(rf"(?<![A-Za-z]){re.escape(v)}(?![A-Za-z])") for v in name_variants(member.get("name", ""))]
        name = member.get("name", "")
        role = str(member.get("role", "")).lower()
        hon, _ = split_name(name)
        if hon and hon.rstrip(".") == "Lady":
            pats.append(re.compile(r"\bher ladyship\b", re.IGNORECASE))
        if hon and hon.rstrip(".") in ("Dr", "Doctor") or "doctor" in role or "physician" in role:
            pats.append(re.compile(r"\bthe doctor\b", re.IGNORECASE))
        if "maid" in role:
            pats.append(re.compile(r"\bthe (?:house)?maid\b", re.IGNORECASE))
        if "butler" in role:
            pats.append(re.compile(r"\bthe butler\b", re.IGNORECASE))
        if "wife" in role or "widow" in role:
            pats.append(re.compile(r"\b(?:his|the) (?:wife|widow)\b", re.IGNORECASE))
        out[sid] = pats
    return out


def mentioned(sentence: str, matchers: dict[str, list[re.Pattern]], exclude: str | None = None) -> list[str]:
    hits: list[tuple[int, str]] = []
    for sid, pats in matchers.items():
        if sid == exclude:
            continue
        for pat in pats:
            m = pat.search(sentence)
            if m:
                hits.append((m.start(), sid))
                break
    return [sid for _, sid in sorted(hits)]


# --------------------------------------------------------------------------------------------------------------------
# Rule-based notebook
# --------------------------------------------------------------------------------------------------------------------


def _speaker(turn: dict) -> str | None:
    actor = turn.get("actor")
    if actor and actor != "detective":
        return str(actor)
    target = turn.get("target")
    return str(target) if target else None


def _evening_bounds(timeline: list[dict]) -> tuple[str, str, bool]:
    times = []
    for ev in timeline or []:
        t = str(ev.get("time", ""))
        if re.match(r"^\d{2}:\d{2}$", t):
            times.append(t)
    if not times:
        return "22:00", "23:59", True
    pm = sum(1 for t in times if int(t[:2]) >= 12 or int(t[:2]) < 6) >= len(times) / 2
    ordered = sorted(times, key=lambda t: _minutes(t) or 0)
    return ordered[0], ordered[-1], pm


def _murder_time(timeline: list[dict], default: str) -> str:
    for ev in timeline or []:
        text = str(ev.get("event", "")).lower()
        if re.search(r"\b(found|dead|body|collapsed|died|killed|murdered|shot|stabbed)\b", text):
            return str(ev.get("time", default))
    return default


def _overlap(a_from: str, a_to: str, b_from: str, b_to: str, slack: int = 10) -> bool:
    af, at, bf, bt = _minutes(a_from), _minutes(a_to), _minutes(b_from), _minutes(b_to)
    if af is None or bf is None:
        return False
    at = at if at is not None else af
    bt = bt if bt is not None else bf
    return af - slack <= bt and bf - slack <= at


def _snippet(text: str, n: int = 110) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def rule_based(visible: dict) -> dict:
    turns = [t for t in (visible.get("turns") or []) if isinstance(t, dict)]
    cast = [c for c in (visible.get("cast") or []) if isinstance(c, dict) and c.get("id")]
    evidence = [e for e in (visible.get("evidence") or []) if isinstance(e, dict) and e.get("id")]
    locations = [loc for loc in (visible.get("locations") or []) if isinstance(loc, dict)]
    timeline = visible.get("timeline_public") or []
    names = {c["id"]: c.get("name", c["id"]) for c in cast}
    start, end, pm = _evening_bounds(timeline)
    loc_pats = _location_patterns(locations)
    matchers = _cast_matchers(cast)

    lines: dict[str, list[tuple[int, str, dict]]] = {c["id"]: [] for c in cast}
    for t in turns:
        sid = _speaker(t)
        spoken = str(t.get("spoken") or "").strip()
        if sid in lines and spoken:
            lines[sid].append((int(t.get("turn") or 0), spoken, t))

    per_suspect: list[dict] = []
    claims_by: dict[str, list[dict]] = {}
    observations: list[dict] = []  # {by, about, where, from, to, quote}
    for sid, sid_lines in lines.items():
        claims: list[dict] = []
        prev_named: list[str] = []
        for turn_no, spoken, _t in sid_lines:
            for sent in split_sentences(spoken):
                times = parse_times(sent, pm)
                loc = find_location(sent, loc_pats)
                whole = bool(_WHOLE_EVENING_RE.search(sent))
                who = mentioned(sent, matchers, exclude=sid)
                if not who and re.search(r"\b(?:them|they|both of them|the two of them|the pair)\b", sent, re.IGNORECASE):
                    who = prev_named
                if who:
                    prev_named = who
                if times:
                    frm, to = times[0][1], times[-1][1] if len(times) > 1 else times[0][1]
                elif whole:
                    frm, to = start, end
                else:
                    frm, to = "", ""
                if who and loc:
                    for oid in who:
                        observations.append({"by": sid, "about": oid, "where": loc[0], "from": frm, "to": to, "quote": sent, "turn": turn_no})
                    # a sighting of someone else is not this suspect's own alibi claim unless it says 'I' too
                    if not re.search(r"\b(?:I|we)\b", sent):
                        continue
                if (times or (loc and (whole or re.search(r"\b(?:I|we|my)\b", sent)))) and (loc or times):
                    claims.append({"quote": sent, "where": loc[0] if loc else "", "from": frm, "to": to})
        claims_by[sid] = claims
        notes = [f"Turn {turn_no}: {_snippet(spoken)}" for turn_no, spoken, _t in sid_lines[-3:]]
        per_suspect.append({"id": sid, "claims": claims, "notes": notes})

    contradictions: list[dict] = []
    seen: set[tuple] = set()

    def add(a_sid: str, a_quote: str, b_ref: str, b_quote: str, note: str) -> None:
        key = (a_sid, a_quote[:40], b_ref, b_quote[:40])
        if key in seen:
            return
        seen.add(key)
        contradictions.append({"a": {"suspect": a_sid, "quote": a_quote}, "b": {"suspect_or_evidence": b_ref, "quote": b_quote}, "note": note})

    # (1) the same suspect in two places at overlapping times
    for sid, claims in claims_by.items():
        placed = [c for c in claims if c["where"]]
        for i in range(len(placed)):
            for j in range(i + 1, len(placed)):
                a, b = placed[i], placed[j]
                if a["where"] == b["where"]:
                    continue
                if a["from"] and b["from"] and _overlap(a["from"], a["to"], b["from"], b["to"]):
                    add(sid, a["quote"], sid, b["quote"], f"{names.get(sid, sid)} places themselves in the {a['where']} and the {b['where']} at the same time.")
    # (2) another suspect's line places them elsewhere
    for obs in observations:
        target = obs["about"]
        for c in claims_by.get(target, []):
            if not c["where"] or c["where"] == obs["where"]:
                continue
            if c["from"] and obs["from"]:
                if not _overlap(c["from"], c["to"], obs["from"], obs["to"], slack=15):
                    continue
                note = f"{names.get(obs['by'], obs['by'])} puts {names.get(target, target)} in the {obs['where']} at {obs['from']}, but {names.get(target, target)} claims the {c['where']}."
            elif not c["from"] and obs["from"]:
                note = f"{names.get(target, target)} never mentioned the {obs['where']}; {names.get(obs['by'], obs['by'])} saw them there at {obs['from']}."
            else:
                note = f"{names.get(obs['by'], obs['by'])} places {names.get(target, target)} in the {obs['where']}, not the {c['where']} they claimed."
            add(target, c["quote"], obs["by"], obs["quote"], note)
    # (3) examined evidence that names a suspect and a place
    for ev in evidence:
        detail = str(ev.get("examined_detail") or "")
        if not detail:
            continue
        for sent in split_sentences(detail):
            loc = find_location(sent, loc_pats)
            if not loc:
                continue
            times = parse_times(sent, pm)
            for oid in mentioned(sent, matchers):
                for c in claims_by.get(oid, []):
                    if not c["where"] or c["where"] == loc[0]:
                        continue
                    if times and c["from"] and not _overlap(c["from"], c["to"], times[0][1], times[-1][1], slack=15):
                        continue
                    add(oid, c["quote"], ev.get("name", ev["id"]), sent, f"{ev.get('name', ev['id'])} places {names.get(oid, oid)} in the {loc[0]}, not the {c['where']}.")

    # suggested next actions
    suggestions: list[str] = []
    asked = {sid for sid, ls in lines.items() if ls}
    presented: set[tuple[str, str]] = set()
    for t in turns:
        if t.get("type") == "present" and t.get("evidence_id") and _speaker(t):
            presented.add((str(t.get("evidence_id")), str(_speaker(t))))
    for con in contradictions:
        a, b = con["a"]["suspect"], con["b"]["suspect_or_evidence"]
        if b in names and a != b:
            suggestions.append(f"Confront {names[a]} and {names[b]} about where {names[a]} really was.")
        elif a in names:
            suggestions.append(f"Press {names[a]} on the contradiction: {_snippet(con['note'], 80)}")
    for ev in evidence:
        detail = str(ev.get("examined_detail") or "")
        if not detail:
            continue
        for oid in mentioned(detail, matchers):
            if (ev["id"], oid) not in presented:
                suggestions.append(f"Present {ev.get('name', ev['id'])} to {names.get(oid, oid)}.")
    when = _murder_time(timeline, end)
    for c in cast:
        if c["id"] not in asked:
            suggestions.append(f"Ask {c.get('name', c['id'])} where they were at {when}.")
    loc_names = {str(loc.get("id")): str(loc.get("name") or loc.get("id")) for loc in locations}
    for ev in evidence:
        if ev.get("examined_detail") or ev.get("state") == "destroyed":
            continue
        loc_name = loc_names.get(str(ev.get("location") or ""), "")
        if loc_name:
            suggestions.append(f"Search {loc_name} to examine {ev.get('name', ev['id'])}.")
        else:
            suggestions.append(f"Examine {ev.get('name', ev['id'])}.")
    for loc in locations:
        if not loc.get("searched"):
            suggestions.append(f"Search {loc.get('name') or loc.get('id')}.")
    if len(suggestions) < 3:
        talkative = sorted(lines, key=lambda s: -len(lines[s]))
        for sid in talkative:
            suggestions.append(f"Press {names.get(sid, sid)} on the gaps in their account.")
            if len(suggestions) >= 3:
                break
    while len(suggestions) < 3:
        suggestions.append("Compare the timeline against every account so far.")
    deduped: list[str] = []
    for s in suggestions:
        if s not in deduped:
            deduped.append(s)
    return {
        "per_suspect": per_suspect,
        "contradictions": contradictions,
        "suggested_next": deduped[:3],
        "turn": int(visible.get("turn") or 0),
    }


# --------------------------------------------------------------------------------------------------------------------
# Gemini path
# --------------------------------------------------------------------------------------------------------------------

WATSON_INSTRUCTION = (
    "You are Watson, keeping a detective's notebook during an interactive murder mystery. You know ONLY what the "
    "detective has personally seen and heard: the transcript below, the examined evidence, the public timeline, the "
    "cast list and the locations. Never invent facts, never guess at hidden information.\n"
    "Fill in the notebook:\n"
    "- per_suspect: for every suspect in the cast, `claims` = each concrete statement they made about where they were "
    "and when (quote their words; `where` in a few words; `from`/`to` as HH:MM 24-hour times when derivable, else "
    "empty strings), and `notes` = up to three short observations about their manner or what they avoided.\n"
    "- contradictions: places where one suspect's claim conflicts with their own earlier claim, with another "
    "suspect's statement, or with examined evidence. Quote both sides.\n"
    "- suggested_next: exactly three concrete next actions (search a named location, present a named piece of "
    "evidence to a named suspect, ask a named suspect a specific question, confront two named suspects on a topic)."
)


def _normalise_entry(raw: dict, visible: dict, fallback: dict) -> dict:
    cast_ids = {c.get("id") for c in (visible.get("cast") or []) if isinstance(c, dict)}
    per_suspect = []
    seen = set()
    for item in raw.get("per_suspect") or []:
        if not isinstance(item, dict) or item.get("id") not in cast_ids or item["id"] in seen:
            continue
        seen.add(item["id"])
        claims = []
        for c in item.get("claims") or []:
            if not isinstance(c, dict):
                continue
            claims.append(
                {
                    "quote": str(c.get("quote") or ""),
                    "where": str(c.get("where") or ""),
                    "from": str(c.get("from") or ""),
                    "to": str(c.get("to") or ""),
                }
            )
        notes = [str(n) for n in (item.get("notes") or []) if str(n).strip()][:5]
        per_suspect.append({"id": item["id"], "claims": claims, "notes": notes})
    for fb in fallback["per_suspect"]:
        if fb["id"] not in seen:
            per_suspect.append(fb)
    contradictions = []
    for con in raw.get("contradictions") or []:
        if not isinstance(con, dict):
            continue
        a, b = con.get("a") or {}, con.get("b") or {}
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        contradictions.append(
            {
                "a": {"suspect": str(a.get("suspect") or ""), "quote": str(a.get("quote") or "")},
                "b": {"suspect_or_evidence": str(b.get("suspect_or_evidence") or ""), "quote": str(b.get("quote") or "")},
                "note": str(con.get("note") or ""),
            }
        )
    suggested = [str(s) for s in (raw.get("suggested_next") or []) if str(s).strip()]
    for s in fallback["suggested_next"]:
        if len(suggested) >= 3:
            break
        if s not in suggested:
            suggested.append(s)
    return {
        "per_suspect": per_suspect,
        "contradictions": contradictions,
        "suggested_next": suggested[:5],
        "turn": int(visible.get("turn") or 0),
    }


async def update(visible: dict, mode: str = "scripted") -> dict[str, Any]:
    """NotebookEntry from player-visible state only."""
    fallback = rule_based(visible)
    if mode != "gemini":
        return fallback
    payload = {
        "turns": visible.get("turns") or [],
        "examined_evidence": [
            {"id": e.get("id"), "name": e.get("name"), "examined_detail": e.get("examined_detail")}
            for e in (visible.get("evidence") or [])
            if isinstance(e, dict) and e.get("examined_detail")
        ],
        "known_evidence": [
            {"id": e.get("id"), "name": e.get("name")} for e in (visible.get("evidence") or []) if isinstance(e, dict) and not e.get("examined_detail")
        ],
        "timeline_public": visible.get("timeline_public") or [],
        "cast": visible.get("cast") or [],
        "locations": visible.get("locations") or [],
        "turn": visible.get("turn"),
    }
    try:
        raw = await llm.call_tool(
            "suspect",
            WATSON_INSTRUCTION,
            [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            NOTEBOOK_UPDATE,
            max_tokens=8000,
            temperature=0.3,
        )
        return _normalise_entry(raw, visible, fallback)
    except (llm.LLMUnavailable, llm.InvalidOutput, llm.NotConfigured) as exc:
        log.warning("watson model unavailable (%s); using rule-based notebook", exc)
        return fallback
