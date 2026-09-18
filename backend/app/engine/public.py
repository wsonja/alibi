"""Player-visible projections of private state (PLAN §9 shapes, INTERFACES §6) and the forbidden-key walker."""
from __future__ import annotations

from typing import Any

from . import stress as stress_mod
from . import world as world_mod

__all__ = [
    "FORBIDDEN_KEYS",
    "forbidden_keys_present",
    "public_cast",
    "public_evidence",
    "public_locations",
    "public_suspect",
    "public_turn",
]

# PLAN §9: never in a non-debug response (the Debrief may carry internal_reasoning/honesty/reveals once closed).
FORBIDDEN_KEYS = frozenset({
    "internal_reasoning", "honesty", "reveals", "wants_to_tell", "points_to", "secrets", "knowledge", "solution",
    "heard_log", "outbox", "stress",
})

public_evidence = world_mod.public_evidence


def _voice(case_suspect: dict) -> dict | None:
    voice = case_suspect.get("voice")
    if not isinstance(voice, dict):
        return None
    out = {k: voice[k] for k in ("webspeech_index", "base_pitch") if k in voice}
    return out or None


def public_suspect(case_suspect: dict, state: dict, turn: int | None = None) -> dict:
    """PublicSuspect. ``silenced`` is true while ``silenced_until`` is set (the Director clears it when it expires);
    pass ``turn`` to evaluate it precisely."""
    silenced_until = state.get("silenced_until")
    if turn is None:
        silenced = silenced_until is not None
    else:
        silenced = silenced_until is not None and int(turn) <= int(silenced_until)
    return {
        "id": case_suspect["id"],
        "name": case_suspect.get("name", case_suspect["id"]),
        "role": case_suspect.get("role", ""),
        "public_description": case_suspect.get("public_description", ""),
        "portrait_prompt": case_suspect.get("portrait_prompt", ""),
        "portrait_url": None,
        "stress_pct": stress_mod.stress_pct(case_suspect, state),
        "emotion": state.get("emotion") or "neutral",
        "tell": state.get("tell") or "",
        "silenced": bool(silenced),
        "last_seen_location": state.get("last_seen_location") or "",
        "voice": _voice(case_suspect),
    }


def public_cast(case: dict, world: dict) -> list[dict]:
    turn = int(world.get("game", {}).get("turn", 0))
    return [public_suspect(s, world["suspects"][s["id"]], turn) for s in case["suspects"] if s["id"] in world["suspects"]]


def public_turn(
    *,
    turn: int,
    seq: int,
    type: str,
    actor: str,
    target: str | None,
    clock: str,
    detective_text: str | None = None,
    tactic: str | None = None,
    evidence_id: str | None = None,
    spoken: str | None = None,
    tell: str | None = None,
    emotion: str | None = None,
    stress_pct: int | None = None,
    other: str | None = None,
) -> dict:
    """PublicTurn. Optional fields are omitted when None."""
    out: dict[str, Any] = {"turn": int(turn), "seq": int(seq), "type": type, "actor": actor, "target": target,
                           "clock": clock}
    for key, value in (
        ("detective_text", detective_text), ("tactic", tactic), ("evidence_id", evidence_id), ("spoken", spoken),
        ("tell", tell), ("emotion", emotion), ("stress_pct", stress_pct), ("other", other),
    ):
        if value is not None:
            out[key] = value
    return out


def public_locations(case: dict, world: dict) -> list[dict]:
    searched = set(world.get("game", {}).get("searched_locations", []))
    return [
        {"id": loc["id"], "name": loc.get("name", loc["id"]), "description": loc.get("description", ""),
         "searched": loc["id"] in searched}
        for loc in case.get("locations", [])
    ]


def forbidden_keys_present(obj: Any) -> list[str]:
    """Walk any nested dict/list structure and return the PLAN §9 forbidden keys found (deduplicated, in order)."""
    found: list[str] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key in FORBIDDEN_KEYS and key not in seen:
                    seen.add(key)
                    found.append(key)
                walk(value)
        elif isinstance(node, (list, tuple, set)):
            for item in node:
                walk(item)

    walk(obj)
    return found
