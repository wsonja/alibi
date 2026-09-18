"""Case Author (PLAN §7.6) — Gemini only.

``write_case(setting, n_suspects, difficulty, progress_cb, notes=...)`` asks the AUTHOR_MODEL for a complete case
document under the ``WRITE_CASE`` schema, with ``vane_hall.json`` verbatim as the one-shot and the hard requirements
spelled out.  Raises ``NotConfigured`` without a credential.  The Checker (``checker.py``) validates the result.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import random
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import client as llm
from .tools import WRITE_CASE

log = logging.getLogger("alibi.agents.author")

_CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ONE_SHOT_PATH = _CASES_DIR / "vane_hall.json"
PERSONAHUB_PATH = _DATA_DIR / "personahub_npc_sample.jsonl"

PORTRAIT_VOCABULARY = (
    "hair colour: dark/black, brown, grey (or 'grey at the temples'), silver, blonde/fair, red/auburn; "
    "hair style: 'brilliantined' (slicked), 'pinned up' (bun); headwear: 'cap' or 'housemaid' (white cap), "
    "'fedora'/'hat'; 'spectacles'/'glasses'; 'moustache', 'beard'; 'pearl' (earrings/necklace); 'cigar'; "
    "'military'/'uniform'; clothing: 'dinner jacket', 'evening dress', 'apron', 'tweed', 'waistcoat'; "
    "skin tone: fair/pale/olive/brown/dark; age words: twenties, thirties, forties, fifty, sixties."
)

DIFFICULTY_GUIDE = {
    "rookie": "Rookie: generous. crack_thresholds around [3, 6, 9]; at least two evidence items initially_known; deflections that hint at the truth; a short public timeline with clear gaps.",
    "detective": "Detective: balanced, like the example. crack_thresholds around [4, 8, 12]; one or two items initially_known; two solid red herrings.",
    "inspector": "Inspector: hard. crack_thresholds around [5, 10, 15]; only one item initially_known; three red herrings; the false-alibi pair should look like collusion in murder; the murderer's framing action should destroy a key piece of motive evidence.",
}


def load_one_shot() -> dict:
    with open(ONE_SHOT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def sample_personas(setting: str, k: int = 8) -> list[str]:
    """6-10 PersonaHub NPC profiles as inspiration, when the sample file exists (seeded by setting)."""
    if not PERSONAHUB_PATH.exists():
        return []
    rows: list[str] = []
    try:
        with open(PERSONAHUB_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = obj.get("persona") or obj.get("input persona") or obj.get("text") or ""
                if isinstance(text, str) and text.strip():
                    rows.append(text.strip())
    except OSError as exc:
        log.warning("could not read %s: %s", PERSONAHUB_PATH, exc)
        return []
    if not rows:
        return []
    rng = random.Random(int(hashlib.sha1(setting.encode("utf-8")).hexdigest()[:8], 16))
    k = max(6, min(10, k))
    return rng.sample(rows, min(k, len(rows)))


def system_instruction() -> str:
    return (
        "You are the Author of an interactive murder mystery in which every suspect is played by a separate AI agent "
        "that sees ONLY its own persona, goals, knowledge and secrets. You write one complete, self-consistent case "
        "document in the exact JSON format of the example. Every field matters: the game engine reads all of them.\n\n"
        "HARD REQUIREMENTS (the case is rejected if any fails):\n"
        "1. Exactly one suspect has \"guilty\": true, and solution.murderer is that suspect's id.\n"
        "2. The murderer's tier-3 secret has \"is_confession\": true and its special_unlocks entry requires at least "
        "one physical evidence id (a requires_any/requires_all condition of the form evidence:<id>).\n"
        "3. solution.proof_paths has at least two ordered paths of 'evidence:<id>' and 'revealed:<secret_id>' tokens, "
        "each satisfiable in order: a 'revealed' token must be unlockable given the evidence/reveals before it.\n"
        "4. At least two red_herrings, and a false-alibi pair among the INNOCENT suspects (two innocents who lie to "
        "cover something that is not the murder).\n"
        "5. Every suspect has 1+ deflections, exactly three secrets with tiers 1, 2 and 3, and key_phrases on every "
        "secret (a Python regex of phrases that would betray it; use alternation like 'gloves|saw (Mr\\\\.? )?Pell').\n"
        "6. Every suspect's relationships object has an entry for every OTHER suspect (type + trust 0-1); "
        "stress_sensitivity has evidence/threaten/flatter/bluff/silence (ints 0-4); crack_thresholds is three "
        "ascending ints; tells has nervous/angry/cracking; personality has nervous/proud/loyal/greedy/guilt_prone.\n"
        "7. Every evidence item is listed in exactly one location's evidence_ids and has a valid location id; "
        "dynamic_evidence items are NOT listed under locations and appear only through a framing action; every id "
        "referenced anywhere (evidence, secrets, locations, suspects) exists. Ids are snake_case.\n"
        "8. Condition DSL tokens only: evidence:<id>, known:<id>, revealed:<secret_id>, stress>=N, flatter_count>=N, "
        "threaten_count>=N, turn>=N, searched:<location_id>, clock>=HH:MM — joined by ' and ' / ' or ', optional "
        "'not ' prefix, no parentheses.\n"
        "9. Times are 24-hour HH:MM. The public timeline is what everyone agrees on; timeline_truth is what really "
        "happened, minute by minute, including the murderer's movements.\n\n"
        "WRITING RULES:\n"
        "- persona, knowledge, secrets (text and cover_story) are written in the THIRD PERSON about the suspect "
        "('She was in the garden.', 'He did not telephone anyone.'); the game turns them into first person.\n"
        "- knowledge is the ONLY factual context the character gets: include everything they would know about the "
        "night, in concrete sentences with times and places, including what they saw of other suspects.\n"
        "- The murderer's knowledge contains the truth of the murder in plain sentences; nobody else's does.\n"
        "- deflections are stage descriptions of how the character changes the subject ('Asks whether the detective "
        "has spoken to X yet, and mentions that …', 'Says …', 'Wonders aloud why …', 'Tells a story about …').\n"
        "- speech_quirk quotes example phrases in single quotes (e.g. says 'Inspector' constantly, 'one' instead of 'I').\n"
        f"- portrait_prompt is a comma-separated list of visual traits using this vocabulary: {PORTRAIT_VOCABULARY}\n"
        "- rumor_seeds: at least one, held by the murderer, spreading a true-but-misleading fact about an innocent.\n"
        "- ticker_lines: 4-6 vague lines that never name anyone.\n"
        "- The murderer has at least one framing_action that hides or destroys evidence if the detective is slow.\n"
        "- Make the cast vivid and period-appropriate to the setting, with distinct voices.\n"
        "Return ONLY the JSON case object."
    )


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug[:40] or "case"


def normalise_case(case: dict, setting: str) -> dict:
    """Light repairs that do not change the story: defaults for optional lists, a stable id, voice indexes."""
    if not isinstance(case, dict):
        return case
    case.setdefault("dynamic_evidence", [])
    case.setdefault("red_herrings", [])
    case.setdefault("rumor_seeds", [])
    case.setdefault("ticker_lines", [])
    case.setdefault("timeline_truth", [])
    title = str(case.get("title") or setting or "Untitled case")
    digest = hashlib.sha1(json.dumps(case, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:6]
    case["id"] = f"{_slug(case.get('id') or title)}_{digest}"
    for i, s in enumerate(case.get("suspects") or []):
        if not isinstance(s, dict):
            continue
        s.setdefault("framing_actions", [])
        s.setdefault("shutdown_rules", {})
        s.setdefault("special_unlocks", {})
        s.setdefault("goals", [])
        s.setdefault("deflections", [])
        if not isinstance(s.get("voice"), dict):
            s["voice"] = {"webspeech_index": i, "base_pitch": 1.0}
        else:
            s["voice"].setdefault("webspeech_index", i)
            s["voice"].setdefault("base_pitch", 1.0)
        if isinstance(s.get("id"), str):
            s["id"] = _slug(s["id"])
        for e_key in ("secrets",):
            for x in s.get(e_key) or []:
                if isinstance(x, dict) and isinstance(x.get("id"), str):
                    x["id"] = _slug(x["id"])
    for e in (case.get("evidence") or []) + (case.get("dynamic_evidence") or []):
        if isinstance(e, dict):
            e.setdefault("initially_known", False)
            e.setdefault("points_to", [])
    case["generated"] = True
    return case


async def _progress(cb: Callable[[str], Any] | None, line: str) -> None:
    log.info("author: %s", line)
    if cb is None:
        return
    try:
        result = cb(line)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:  # noqa: BLE001 - a broken progress sink must not break the pipeline
        log.debug("progress callback failed: %s", exc)


async def write_case(
    setting: str,
    n_suspects: int,
    difficulty: str,
    progress_cb: Callable[[str], Any] | None = None,
    *,
    notes: list[str] | None = None,
) -> dict:
    """Ask the AUTHOR_MODEL for a new case. Raises NotConfigured without a Gemini credential."""
    if not llm.credential_available():
        raise llm.NotConfigured(
            "Generating a case needs a Gemini API key: set GEMINI_API_KEY in backend/.env (or paste it in Settings)."
        )
    n_suspects = max(3, min(6, int(n_suspects or 4)))
    difficulty = (difficulty or "detective").lower()
    if difficulty not in DIFFICULTY_GUIDE:
        difficulty = "detective"
    one_shot = load_one_shot()
    personas = sample_personas(setting)
    await _progress(progress_cb, f"Author: writing a {difficulty} case with {n_suspects} suspects set in {setting.strip() or 'an undisclosed place'}…")

    user_parts = [
        f"Setting: {setting.strip()}",
        f"Number of suspects: exactly {n_suspects}",
        f"Difficulty: {difficulty}. {DIFFICULTY_GUIDE[difficulty]}",
    ]
    if personas:
        user_parts.append("Character inspiration (loose; adapt freely to the period and setting):\n" + "\n".join(f"- {p}" for p in personas))
    user_parts.append(
        "Here is a complete example case, verbatim, as the one-shot. Match its format, depth and tone exactly, but "
        "invent a NEW story, cast, victim, evidence and solution for the setting above:\n```json\n"
        + json.dumps(one_shot, ensure_ascii=False, indent=1)
        + "\n```"
    )
    if notes:
        user_parts.append(
            "Your previous draft was rejected by the consistency checker. Fix ALL of these problems in the new draft:\n"
            + "\n".join(f"- {n}" for n in notes)
        )
    user_parts.append("Write the new case now. Return only the JSON object.")
    messages = [{"role": "user", "content": "\n\n".join(user_parts)}]

    case = await llm.call_tool("author", system_instruction(), messages, WRITE_CASE, max_tokens=32000, temperature=1.0)
    info = llm.last_call_info()
    case = normalise_case(case, setting)
    n_ev = len(case.get("evidence") or [])
    await _progress(
        progress_cb,
        f"Author: received \"{case.get('title', 'untitled')}\" — {len(case.get('suspects') or [])} suspects, {n_ev} evidence items "
        f"({info.get('model')}, {info.get('latency_ms')} ms).",
    )
    return case


__all__ = ["load_one_shot", "normalise_case", "sample_personas", "system_instruction", "write_case"]
