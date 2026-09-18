"""heard_log, outbox, off-screen ticks and rumors (PLAN §8.7)."""
from __future__ import annotations

import random

__all__ = [
    "TRUSTED_TYPES",
    "TRUST_THRESHOLD",
    "add_heard",
    "can_deliver",
    "pick_ticker",
    "queue_rumor_seeds",
    "queue_wants_to_tell",
    "run_offscreen_tick",
    "should_tick",
]

TRUSTED_TYPES = {"lover", "ally", "trusts"}
TRUST_THRESHOLD = 0.5


def add_heard(world: dict, to_id: str, from_id: str, text: str, turn: int, channel: str) -> dict:
    entry = {"from": from_id, "text": text, "turn": int(turn), "channel": channel}
    world["suspects"][to_id].setdefault("heard_log", []).append(entry)
    return entry


def queue_wants_to_tell(case: dict, world: dict, from_id: str, wants: list, turn: int) -> list[dict]:
    """Append validated ``wants_to_tell`` items to ``from_id``'s outbox. Returns the queued items."""
    ids = {s["id"] for s in case.get("suspects", [])}
    outbox = world["suspects"][from_id].setdefault("outbox", [])
    queued: list[dict] = []
    for want in wants or []:
        if not isinstance(want, dict):
            continue
        to = want.get("to")
        text = want.get("message", want.get("text"))
        if to not in ids or to == from_id or not isinstance(text, str) or not text.strip():
            continue
        item = {"to": to, "text": text.strip(), "queued_turn": int(turn)}
        outbox.append(item)
        queued.append(item)
    return queued


def should_tick(turn: int, difficulty: str, every: int) -> bool:
    """Every ``every`` player turns (inspector: every 2)."""
    period = 2 if difficulty == "inspector" else int(every or 0)
    if period <= 0 or int(turn) <= 0:
        return False
    return int(turn) % period == 0


def can_deliver(case_suspect_from: dict, item: dict) -> bool:
    """Trust rule: trust >= 0.5, or relationship type in {lover, ally, trusts}, or the item is a rumor seed."""
    if item.get("seed"):
        return True
    rel = (case_suspect_from.get("relationships") or {}).get(item.get("to")) or {}
    try:
        trust = float(rel.get("trust", 0.0))
    except (TypeError, ValueError):
        trust = 0.0
    return trust >= TRUST_THRESHOLD or rel.get("type") in TRUSTED_TYPES


def queue_rumor_seeds(case: dict, world: dict, turn: int) -> list[dict]:
    """Queue every rumor seed into its holder's outbox (marked ``seed`` so trust never blocks it)."""
    queued: list[dict] = []
    ids = set(world["suspects"])
    for seed in case.get("rumor_seeds", []) or []:
        holder = seed.get("holder")
        if holder not in ids:
            continue
        outbox = world["suspects"][holder].setdefault("outbox", [])
        for to in seed.get("spreads_to", []) or []:
            if to not in ids or to == holder:
                continue
            item = {"to": to, "text": seed.get("text", ""), "queued_turn": int(turn), "seed": True,
                    "intent": seed.get("intent")}
            outbox.append(item)
            queued.append(item)
    return queued


def run_offscreen_tick(case: dict, world: dict, rng: random.Random, *, dropped: list | None = None) -> list[dict]:
    """Drain every outbox. On the first tick the case's rumor seeds are queued first.
    Delivered items land in the target's heard_log (channel "private") and are returned as
    ``[{from, to, text, turn, channel}]``; undeliverable items are discarded (collected into ``dropped`` if given).
    ``rng`` is accepted for signature parity; delivery itself is deterministic."""
    game = world["game"]
    turn = int(game.get("turn", 0))
    if int(game.get("offscreen_ticks", 0)) == 0:
        queue_rumor_seeds(case, world, turn)
    by_id = {s["id"]: s for s in case.get("suspects", [])}
    deliveries: list[dict] = []
    for sid in [s["id"] for s in case.get("suspects", [])] + [x for x in world["suspects"] if x not in by_id]:
        state = world["suspects"].get(sid)
        if state is None:
            continue
        items = list(state.get("outbox", []))
        state["outbox"] = []
        for item in items:
            to = item.get("to")
            if to not in world["suspects"] or to == sid:
                continue
            record = {"from": sid, "to": to, "text": item.get("text", ""), "turn": turn, "channel": "private",
                      "seed": bool(item.get("seed")), "queued_turn": item.get("queued_turn")}
            if can_deliver(by_id.get(sid, {}), item):
                add_heard(world, to, sid, item.get("text", ""), turn, "private")
                deliveries.append(record)
            elif dropped is not None:
                dropped.append(record)
    game["offscreen_ticks"] = int(game.get("offscreen_ticks", 0)) + 1
    return deliveries


def pick_ticker(case: dict, rng: random.Random) -> str | None:
    lines = case.get("ticker_lines") or []
    if not lines:
        return None
    return rng.choice(lines)
