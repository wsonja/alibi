"""State snapshot / restore (PLAN §5, §8.10). The World dict *is* the snapshot."""
from __future__ import annotations

import copy

__all__ = ["restore", "take"]

_REQUIRED_TOP = ("game", "suspects", "evidence")


def take(world: dict) -> dict:
    """Deep copy of the world, safe to persist as JSON."""
    return copy.deepcopy(world)


def restore(snapshot: dict) -> dict:
    """Deep copy of a persisted snapshot back into a live World. Missing top-level keys are filled in."""
    if not isinstance(snapshot, dict):
        raise TypeError("snapshot must be a dict")
    world = copy.deepcopy(snapshot)
    for key in _REQUIRED_TOP:
        world.setdefault(key, {})
    game = world["game"]
    game.setdefault("turn", 0)
    game.setdefault("clock_minutes", 15)
    game.setdefault("status", "investigating")
    game.setdefault("difficulty", "detective")
    game.setdefault("searched_locations", [])
    game.setdefault("fired_framing_actions", [])
    game.setdefault("offscreen_ticks", 0)
    game.setdefault("tactics_used", {})
    game.setdefault("composure_samples", [])
    return world
