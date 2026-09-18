"""Stress ("pressure") math and unlock tiers (PLAN §8.2–§8.4).

The number called ``stress`` in code is the pressure-to-talk; the UI labels it *Pressure*.
"""
from __future__ import annotations

import math
from typing import Any

from . import conditions

__all__ = [
    "DIFFICULTY_FACTOR",
    "TACTICS",
    "apply_decay",
    "apply_delta",
    "clamp",
    "compute_delta",
    "is_unlockable_tier",
    "locked_secret_ids",
    "near_cracks",
    "recompute_unlocks",
    "round_half_up",
    "stress_pct",
    "thresholds",
]

DIFFICULTY_FACTOR = {"rookie": 1.5, "detective": 1.0, "inspector": 0.75}
TACTICS = ("bluff", "flatter", "threaten", "silence")
COMPOSURE_TACTICS = ("bluff", "threaten")
MODEL_DELTA_MIN, MODEL_DELTA_MAX = -2, 3
DELTA_MIN, DELTA_MAX = -2, 5
NEAR_CRACK_MARGIN = 2


def clamp(value: float, lo: float, hi: float) -> int | float:
    return max(lo, min(hi, value))


def round_half_up(x: float) -> int:
    """Round with .5 going up (Python's round() is banker's rounding)."""
    return math.floor(x + 0.5)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return round(float(value))
    except (TypeError, ValueError):
        return default


def compute_delta(
    model_delta: int,
    *,
    tactic: str | None,
    evidence_points_to_self: bool | None,
    sensitivity: dict[str, int],
    composure: str | None,
    difficulty: str,
) -> int:
    """PLAN §8.2.

    ``tactic`` is one of bluff|flatter|threaten|silence for tactic turns, else None.
    ``evidence_points_to_self`` is None on non-present turns, otherwise whether the presented evidence's
    ``points_to`` names this suspect.
    """
    sensitivity = sensitivity or {}
    md = int(clamp(_to_int(model_delta), MODEL_DELTA_MIN, MODEL_DELTA_MAX))
    tactic_bonus = (_to_int(sensitivity.get(tactic, 1)) - 1) if tactic in TACTICS else 0
    if evidence_points_to_self is None:
        evidence_bonus = 0
    else:
        evidence_bonus = _to_int(sensitivity.get("evidence", 0)) if evidence_points_to_self else -1
    composure_mod = 0
    if tactic in COMPOSURE_TACTICS:
        composure_mod = {"nervous": -1, "confident": 1}.get(composure or "", 0)
    delta = int(clamp(md + tactic_bonus + evidence_bonus + composure_mod, DELTA_MIN, DELTA_MAX))
    if delta > 0:
        delta = round_half_up(delta * DIFFICULTY_FACTOR.get(difficulty, 1.0))
    return delta


def apply_delta(world: dict, suspect_id: str, delta: int) -> tuple[int, int]:
    """stress = max(0, stress + delta). Returns (before, after)."""
    state = world["suspects"][suspect_id]
    before = int(state.get("stress", 0))
    after = max(0, before + int(delta))
    state["stress"] = after
    return before, after


def apply_decay(world: dict, addressed_ids) -> dict[str, int]:
    """Every suspect not addressed this turn loses 1 (min 0). Returns {suspect_id: new stress} for the decayed."""
    addressed = set(addressed_ids or ())
    decayed: dict[str, int] = {}
    for sid, state in world["suspects"].items():
        if sid in addressed:
            continue
        before = int(state.get("stress", 0))
        after = max(0, before - 1)
        state["stress"] = after
        if after != before:
            decayed[sid] = after
    return decayed


def thresholds(case_suspect: dict) -> list[int]:
    t = list(case_suspect.get("crack_thresholds") or [])
    while len(t) < 3:
        t.append(t[-1] if t else 0)
    return [int(x) for x in t[:3]]


def stress_pct(case_suspect: dict, state: dict) -> int:
    """0–100 of t3, capped at 100."""
    t3 = thresholds(case_suspect)[2]
    stress = int(state.get("stress", 0))
    if t3 <= 0:
        return 100 if stress > 0 else 0
    return int(min(100, round(100 * stress / t3)))


def is_unlockable_tier(case_suspect: dict, stress: int, tier: int) -> bool:
    """True when ``stress`` reaches the crack threshold for ``tier`` (1..3)."""
    t = thresholds(case_suspect)
    idx = int(clamp(int(tier) - 1, 0, 2))
    return int(stress) >= t[idx]


def _case_suspect(case: dict, suspect_id: str) -> dict:
    for s in case["suspects"]:
        if s["id"] == suspect_id:
            return s
    raise KeyError(suspect_id)


def recompute_unlocks(case: dict, world: dict, suspect_id: str) -> list[str]:
    """PLAN §8.3. Monotonic: writes ``unlocked_secret_ids`` (case secret order) and returns it."""
    suspect = _case_suspect(case, suspect_id)
    state = world["suspects"][suspect_id]
    ctx = conditions.context_for(case, world, suspect_id)
    already = set(state.get("unlocked_secret_ids", []))
    rules = suspect.get("special_unlocks") or {}
    unlocked: list[str] = []
    for secret in suspect.get("secrets", []):
        sid = secret["id"]
        if sid in already:
            unlocked.append(sid)
            continue
        if is_unlockable_tier(suspect, ctx["stress"], secret.get("tier", 3)) and conditions.rule_holds(rules.get(sid), ctx):
            unlocked.append(sid)
    state["unlocked_secret_ids"] = unlocked
    return list(unlocked)


def locked_secret_ids(case_suspect: dict, state: dict) -> list[str]:
    unlocked = set(state.get("unlocked_secret_ids", []))
    return [s["id"] for s in case_suspect.get("secrets", []) if s["id"] not in unlocked]


def near_cracks(case: dict, world: dict) -> list[dict]:
    """Locked, unrevealed secrets whose tier threshold is within NEAR_CRACK_MARGIN of the suspect's stress,
    or whose stress suffices but the special unlock is missing."""
    out: list[dict] = []
    for suspect in case["suspects"]:
        sid = suspect["id"]
        state = world["suspects"].get(sid)
        if state is None:
            continue
        unlocked = set(state.get("unlocked_secret_ids", []))
        revealed = set(state.get("revealed_secret_ids", []))
        t = thresholds(suspect)
        stress = int(state.get("stress", 0))
        for secret in suspect.get("secrets", []):
            secret_id = secret["id"]
            if secret_id in unlocked or secret_id in revealed:
                continue
            threshold = t[int(clamp(int(secret.get("tier", 3)) - 1, 0, 2))]
            if threshold - stress <= NEAR_CRACK_MARGIN:
                out.append({"suspect_id": sid, "secret_id": secret_id, "stress": stress, "threshold": threshold})
    return out
