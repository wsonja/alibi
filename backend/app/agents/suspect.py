"""Suspect prompt builder (PLAN §7.2) and the Gemini performer.

Everything here is built from the PerformContext alone (INTERFACES §3): this suspect's persona, goals, knowledge,
secrets, deflections and state.  Nothing about any other suspect or the solution can enter, because it is not in
``ctx`` to begin with.
"""

from __future__ import annotations

import logging
from typing import Any

from . import client as llm
from .tools import RESPOND_AS_CHARACTER

log = logging.getLogger("alibi.agents.suspect")

KEEP_VERBATIM = 30  # messages kept verbatim; older ones are summarised (PLAN §7.2)

COMPOSURE_PHRASES = {
    "nervous": "seems nervous: blinking a lot, avoiding your eyes",
    "confident": "is steady and unblinking",
}
GAZE_PHRASES = {
    "evidence": ", and keeps glancing at the evidence table",
    "notebook": ", and keeps checking their notes",
    "away": ", and isn't really looking at you",
}


def _bullets(items: list[str] | None) -> str:
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    return "\n".join(f"- {i}" for i in items) if items else "- (nothing)"


def build_block_a(ctx: dict) -> str:
    """Block A — stable per game (byte-stable so implicit caching can hit)."""
    s = ctx["suspect"]
    case = ctx.get("case") or {}
    secret_lines = []
    for sec in s.get("secrets", []):
        line = f"- [{sec['id']}] tier {sec.get('tier', '?')}: {sec.get('text', '')}"
        if sec.get("cover_story"):
            line += f"\n  Cover story: {sec['cover_story']}"
        secret_lines.append(line)
    secrets_text = "\n".join(secret_lines) if secret_lines else "- (none)"
    return (
        f"You are {s['name']}, {s.get('role', '')}, in an interactive murder mystery set in {case.get('setting', '')}.\n"
        f"Persona: {s.get('persona', '')}\n"
        f"How you speak: {s.get('speech_quirk', '')}\n"
        "What you want:\n"
        f"{_bullets(s.get('goals'))}\n"
        "What you know for certain — this is ALL you know about the night; do not invent facts beyond this:\n"
        f"{_bullets(s.get('knowledge'))}\n"
        "Your secrets. Protect LOCKED ones with lies, deflection, or your cover story. Confess an UNLOCKED one only if genuinely pressed.\n"
        f"{secrets_text}\n"
        "Ways you tend to change the subject:\n"
        f"{_bullets(s.get('deflections'))}\n"
        "Things other people have told you are hearsay. You may repeat them only if it serves what you want.\n"
        "Rules:\n"
        '- Stay in character. Never mention being an AI, a game, rules, tiers, or "secrets" as a concept.\n'
        "- Speak in 1–4 sentences. No stage directions in `spoken`; put physical reactions in `tell`.\n"
        "- You may lie. Lies must be consistent with your cover story and with what you have already said.\n"
        "- If the detective claims to know something you have not been shown evidence of, treat it as a bluff unless it matches what you have heard.\n"
        "- Never state a LOCKED secret, paraphrase it, or confirm it if guessed. If cornered, deflect, get angry, or go quiet."
    )


def observation_line(player_signal: dict | None) -> str | None:
    """The 'Observation: the detective ...' line, or None when there is nothing to observe."""
    if not player_signal:
        return None
    composure = str(player_signal.get("composure") or "").lower()
    gaze = str(player_signal.get("gaze") or "").lower()
    try:
        voice = float(player_signal.get("voice_stress") or 0)
    except (TypeError, ValueError):
        voice = 0.0
    if not composure and voice > 0.7:
        composure = "nervous"  # PLAN §8.5
    comp_phrase = COMPOSURE_PHRASES.get(composure, "")
    gaze_phrase = GAZE_PHRASES.get(gaze, "")
    if comp_phrase:
        return f"Observation: the detective {comp_phrase}{gaze_phrase}."
    if gaze_phrase:
        # neutral composure omits its phrase; keep the gaze observation as a sentence of its own
        return f"Observation: the detective {gaze_phrase[len(', and '):]}."
    return None


def is_silenced(ctx: dict) -> bool:
    state = ctx.get("state") or {}
    until = state.get("silenced_until")
    if until is None:
        return False
    turn = ctx.get("turn")
    if turn is None:
        turn = state.get("turn")
    try:
        return turn is None or int(turn) < int(until)
    except (TypeError, ValueError):
        return False


def build_block_b(ctx: dict) -> str:
    """Block B — dynamic per turn."""
    s = ctx["suspect"]
    state = ctx.get("state") or {}
    names = ctx.get("cast_names") or {}
    thresholds = s.get("crack_thresholds") or [4, 8, 12]
    t3 = thresholds[2] if len(thresholds) >= 3 else thresholds[-1]
    unlocked = ", ".join(ctx.get("unlocked") or []) or "none"
    locked = ", ".join(ctx.get("locked") or []) or "none"
    heard = state.get("heard_log") or []
    heard_lines = [
        f"- (turn {h.get('turn', '?')}, from {names.get(h.get('from'), h.get('from', '?'))}) {h.get('text', '')}"
        for h in heard
    ]
    lines = [
        f"Current pressure: {state.get('stress', 0)} (0 = calm, {t3}+ = breaking).",
        f"UNLOCKED secret ids (you may reveal if pressed): {unlocked}",
        f"LOCKED secret ids (never reveal): {locked}",
        "Things you have heard from others so far:",
        "\n".join(heard_lines) if heard_lines else "- nothing",
    ]
    if is_silenced(ctx):
        lines.append("You have decided not to cooperate for now.")
    obs = observation_line(ctx.get("player_signal"))
    if obs:
        lines.append(obs)
    other = ctx.get("confrontation_with")
    if other:
        other_name = other.get("name") or names.get(other.get("id"), other.get("id"))
        lines.append(
            f"You are in the room with {other_name}. The detective is listening. Address {other_name} directly."
        )
    retry_ids = ctx.get("retry_ids") or []
    if retry_ids:
        lines.append(
            f"Your previous answer gave away too much about {', '.join(retry_ids)}. Answer again without revealing it."
        )
    return "\n".join(lines)


def build_system_blocks(ctx: dict) -> list[str]:
    """[Block A, Block B] — the exact system text for this turn (also what the Judge Panel shows)."""
    return [build_block_a(ctx), build_block_b(ctx)]


async def build_messages(ctx: dict) -> list[dict]:
    """The suspect's conversation (assistant -> model) plus the new user message, summarising anything past 30."""
    state = ctx.get("state") or {}
    conversation = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in (state.get("conversation") or [])
        if isinstance(m, dict)
    ]
    messages: list[dict] = []
    if len(conversation) > KEEP_VERBATIM:
        older, recent = conversation[:-KEEP_VERBATIM], conversation[-KEEP_VERBATIM:]
        summary = ctx.get("conversation_summary") or state.get("conversation_summary")
        if not summary:
            from . import judge

            summary = await judge.summarize(older, "gemini")
            ctx["conversation_summary"] = summary
        messages.append({"role": "user", "content": f"Earlier in the conversation: {summary}"})
        messages.extend(recent)
    else:
        messages.extend(conversation)
    messages.append({"role": "user", "content": ctx.get("user_message") or "Detective: Well?"})
    return llm.normalise_messages(messages)


class GeminiPerformer:
    """One Gemini call per suspect per turn (PLAN §2.1)."""

    mode = "gemini"

    def __init__(self, model: str = "suspect", *, temperature: float = 0.9, max_tokens: int = 1200):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def perform(self, ctx: dict) -> dict[str, Any]:
        blocks = build_system_blocks(ctx)
        ctx["system_blocks"] = blocks
        messages = await build_messages(ctx)
        system_text = blocks[0] + "\n\n" + blocks[1]
        raw = await llm.call_tool(
            self.model,
            system_text,
            messages,
            RESPOND_AS_CHARACTER,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        info = llm.last_call_info()
        log.info(
            "suspect turn %s type=%s model=%s latency_ms=%s",
            ctx["suspect"].get("id"),
            ctx.get("turn_type"),
            info.get("model"),
            info.get("latency_ms"),
        )
        return raw
