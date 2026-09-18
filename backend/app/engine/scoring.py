"""Accusation scoring (PLAN §8.9)."""
from __future__ import annotations

__all__ = ["METHOD_POINTS", "MURDERER_POINTS", "confidence_badge", "rank", "score"]

MURDERER_POINTS = 60
METHOD_POINTS = 20
MOTIVE_POINTS_ALLOWED = (0, 10, 20)


def score(case: dict, suspect_id: str, method_evidence_ids, motive_points: int) -> dict:
    """``{murderer, method, motive, total}``. ``motive_points`` is the judge's grade (0|10|20)."""
    solution = case.get("solution") or {}
    murderer = MURDERER_POINTS if suspect_id == solution.get("murderer") else 0
    method_ids = set(method_evidence_ids or [])
    method = METHOD_POINTS if method_ids & set(solution.get("method_evidence_ids") or []) else 0
    try:
        motive = int(motive_points or 0)
    except (TypeError, ValueError):
        motive = 0
    motive = max(0, min(20, motive))
    if motive not in MOTIVE_POINTS_ALLOWED:
        motive = min(MOTIVE_POINTS_ALLOWED, key=lambda p: abs(p - motive))
    return {"murderer": murderer, "method": method, "motive": motive, "total": murderer + method + motive}


def rank(total: int) -> str:
    if total >= 90:
        return "Inspector"
    if total >= 60:
        return "Detective"
    return "Rookie"


def confidence_badge(conf) -> str | None:
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return None
    if c >= 0.8:
        return "bold call"
    if c <= 0.3:
        return "hedged"
    return None
