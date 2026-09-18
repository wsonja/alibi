"""Leak Guard (PLAN §7.4).

``check(spoken, locked_secrets, mode)`` returns ``{"leaked": [secret_id, ...], "reason": str}``.

* The ``key_phrases`` regex of every locked secret is always tested against the spoken line (case-insensitive).
* In gemini mode a cheap GUARD_MODEL call also reads the line against the locked secrets' texts; the two verdicts are
  unioned.  If the model is unavailable the regex verdict stands alone.
* The call is skipped when nothing is locked.
"""

from __future__ import annotations

import logging
import re

from . import client as llm
from .tools import LEAK_CHECK

log = logging.getLogger("alibi.agents.leak_guard")

GUARD_INSTRUCTION = (
    "You are the leak guard for an interactive murder mystery. You will be shown one statement spoken by a character "
    "and a list of that character's LOCKED secrets. Does the statement disclose, confirm, or unmistakably imply any of "
    "these secrets? A denial, a lie, or a cover story is not a leak. Return only ids that are actually disclosed. "
    "Answer with a JSON object {\"leaked\": [ids], \"reason\": \"one sentence\"}."
)


def regex_check(spoken: str, locked_secrets: list[dict]) -> list[str]:
    """Ids of locked secrets whose ``key_phrases`` regex matches the line."""
    hits: list[str] = []
    text = spoken or ""
    for sec in locked_secrets or []:
        pat = sec.get("key_phrases")
        sid = sec.get("id")
        if not pat or not sid:
            continue
        try:
            if re.search(pat, text, re.IGNORECASE):
                hits.append(sid)
        except re.error as exc:
            log.warning("bad key_phrases regex for %s: %s", sid, exc)
    return hits


async def model_check(spoken: str, locked_secrets: list[dict]) -> dict:
    """The GUARD_MODEL verdict. Raises LLMUnavailable / InvalidOutput / NotConfigured like call_tool."""
    listing = "\n".join(f"- {sec.get('id')}: {sec.get('text', '')}" for sec in locked_secrets)
    user = f"Statement:\n{spoken}\n\nLocked secrets:\n{listing}"
    raw = await llm.call_tool(
        "guard",
        GUARD_INSTRUCTION,
        [{"role": "user", "content": user}],
        LEAK_CHECK,
        max_tokens=1200,
        temperature=0.0,
    )
    known = {sec.get("id") for sec in locked_secrets}
    leaked = raw.get("leaked") or []
    if isinstance(leaked, str):
        leaked = [leaked]
    leaked = [str(x) for x in leaked if str(x) in known]
    return {"leaked": leaked, "reason": str(raw.get("reason") or "")}


async def check(spoken: str, locked_secrets: list[dict], mode: str = "scripted") -> dict:
    """Union of the regex check and (in gemini mode) the model check."""
    locked_secrets = [s for s in (locked_secrets or []) if isinstance(s, dict) and s.get("id")]
    if not locked_secrets or not (spoken or "").strip():
        return {"leaked": [], "reason": "nothing locked" if not locked_secrets else "empty line"}
    regex_hits = regex_check(spoken, locked_secrets)
    reasons: list[str] = []
    if regex_hits:
        reasons.append(f"key phrase matched for {', '.join(regex_hits)}")
    leaked = list(regex_hits)
    if mode == "gemini":
        try:
            verdict = await model_check(spoken, locked_secrets)
            for sid in verdict["leaked"]:
                if sid not in leaked:
                    leaked.append(sid)
            if verdict["reason"]:
                reasons.append(f"guard model: {verdict['reason']}")
        except (llm.LLMUnavailable, llm.InvalidOutput, llm.NotConfigured) as exc:
            log.warning("leak guard model unavailable (%s); regex verdict only", exc)
            reasons.append("guard model unavailable; regex only")
    if not reasons:
        reasons.append("clean")
    return {"leaked": leaked, "reason": "; ".join(reasons)}
