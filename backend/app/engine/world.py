"""Evidence, locations, clock and framing actions (PLAN §8.8) plus the initial World (INTERFACES §1)."""
from __future__ import annotations

import random
from typing import Any

from . import conditions

__all__ = [
    "CLOCK_COST",
    "CLOCK_START_MINUTES",
    "advance_clock",
    "all_evidence",
    "clock_str",
    "default_location",
    "dynamic_evidence_ids",
    "evaluate_framing_actions",
    "evidence_index",
    "evidence_text_for_present",
    "examined_ids",
    "initial_suspect_state",
    "initial_world",
    "is_presentable",
    "known_or_examined_ids",
    "location_index",
    "location_of_evidence",
    "public_evidence",
    "public_evidence_item",
    "search",
]

CLOCK_START_MINUTES = 15  # 00:15, the night of the murder
CLOCK_COST = {"ask": 5, "tactic": 5, "present": 5, "search": 10, "confront": 15, "accuse": 0}
DEFAULT_LOCATION_ID = "drawing_room"


# ----------------------------------------------------------------------------- case helpers

def all_evidence(case: dict) -> list[dict]:
    """Static evidence followed by dynamic evidence, in case order."""
    return list(case.get("evidence", [])) + list(case.get("dynamic_evidence", []))


def evidence_index(case: dict) -> dict[str, dict]:
    return {e["id"]: e for e in all_evidence(case)}


def dynamic_evidence_ids(case: dict) -> set[str]:
    return {e["id"] for e in case.get("dynamic_evidence", [])}


def location_index(case: dict) -> dict[str, dict]:
    return {loc["id"]: loc for loc in case.get("locations", [])}


def default_location(case: dict) -> str:
    ids = [loc["id"] for loc in case.get("locations", [])]
    if DEFAULT_LOCATION_ID in ids:
        return DEFAULT_LOCATION_ID
    return ids[0] if ids else ""


def location_of_evidence(case: dict, evidence_id: str) -> str | None:
    ev = evidence_index(case).get(evidence_id)
    return ev.get("location") if ev else None


# ----------------------------------------------------------------------------- initial state

def initial_suspect_state(case: dict, case_suspect: dict) -> dict:
    return {
        "suspect_id": case_suspect["id"],
        "stress": 0,
        "unlocked_secret_ids": [],
        "revealed_secret_ids": [],
        "heard_log": [],
        "outbox": [],
        "flatter_count": 0,
        "threaten_count": 0,
        "silenced_until": None,
        "emotion": "neutral",
        "tell": "",
        "last_seen_location": default_location(case),
        "conversation": [],
        "last_internal_reasoning": "",
        "last_honesty": "",
        "last_accuses": None,
        "last_system_blocks": [],
    }


def initial_world(case: dict, difficulty: str) -> dict:
    evidence: dict[str, dict] = {}
    for e in case.get("evidence", []):
        evidence[e["id"]] = {"state": "known" if e.get("initially_known") else "hidden", "examined_turn": None}
    for e in case.get("dynamic_evidence", []):
        evidence[e["id"]] = {"state": "hidden", "examined_turn": None}
    return {
        "game": {
            "turn": 0,
            "clock_minutes": CLOCK_START_MINUTES,
            "status": "briefing",
            "difficulty": difficulty or "detective",
            "searched_locations": [],
            "fired_framing_actions": [],
            "offscreen_ticks": 0,
            "tactics_used": {},
            "composure_samples": [],
        },
        "suspects": {s["id"]: initial_suspect_state(case, s) for s in case.get("suspects", [])},
        "evidence": evidence,
    }


# ----------------------------------------------------------------------------- clock

def advance_clock(world: dict, minutes: int) -> int:
    game = world["game"]
    game["clock_minutes"] = int(game.get("clock_minutes", CLOCK_START_MINUTES)) + int(minutes)
    return game["clock_minutes"]


def clock_str(minutes: int) -> str:
    minutes = int(minutes)
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


# ----------------------------------------------------------------------------- evidence state

def examined_ids(world: dict) -> set[str]:
    return {eid for eid, st in world.get("evidence", {}).items() if st.get("state") == "examined"}


def known_or_examined_ids(world: dict) -> set[str]:
    return {eid for eid, st in world.get("evidence", {}).items() if st.get("state") in ("known", "examined")}


def is_presentable(world: dict, evidence_id: str) -> bool:
    st = world.get("evidence", {}).get(evidence_id)
    return bool(st) and st.get("state") in ("known", "examined")


def _evidence_present_at(case: dict, world: dict, location_id: str) -> list[dict]:
    """Evidence physically discoverable at a location: static items there, plus dynamic items that have appeared."""
    dynamic = dynamic_evidence_ids(case)
    out = []
    for e in all_evidence(case):
        if e.get("location") != location_id:
            continue
        st = world["evidence"].get(e["id"])
        if st is None:
            continue
        if e["id"] in dynamic and st.get("state") == "hidden":
            continue  # not in the world yet
        out.append(e)
    return out


def search(case: dict, world: dict, location_id: str) -> list[str]:
    """PLAN §8.8: hidden|known evidence at the location becomes examined; clock +10; location recorded.
    Returns the newly examined evidence ids (a second search returns nothing)."""
    if location_id not in location_index(case):
        raise KeyError(f"unknown location {location_id!r}")
    game = world["game"]
    turn = int(game.get("turn", 0))
    newly: list[str] = []
    for e in _evidence_present_at(case, world, location_id):
        st = world["evidence"][e["id"]]
        if st.get("state") in ("hidden", "known"):
            st["state"] = "examined"
            st["examined_turn"] = turn
            newly.append(e["id"])
    if location_id not in game.setdefault("searched_locations", []):
        game["searched_locations"].append(location_id)
    advance_clock(world, CLOCK_COST["search"])
    return newly


def evidence_text_for_present(case: dict, world: dict, evidence_id: str) -> str:
    ev = evidence_index(case)[evidence_id]
    st = world["evidence"].get(evidence_id, {})
    if st.get("state") == "examined":
        return ev.get("examined_detail") or ev.get("description") or ""
    return ev.get("description") or ""


def _was_visible(ev: dict, st: dict) -> bool:
    """Whether the player ever knew of this item (used to decide if a destroyed item is still listed)."""
    if st.get("state") in ("known", "examined"):
        return True
    if st.get("state") == "destroyed":
        return bool(ev.get("initially_known")) or st.get("examined_turn") is not None or bool(st.get("was_known"))
    return False


def public_evidence_item(ev: dict, st: dict) -> dict:
    item = {
        "id": ev["id"],
        "name": ev.get("name", ev["id"]),
        "location": ev.get("location"),
        "state": st.get("state", "hidden"),
        "description": ev.get("description", ""),
    }
    if st.get("state") == "examined":
        item["examined_detail"] = ev.get("examined_detail", "")
    return item


def public_evidence(case: dict, world: dict) -> list[dict]:
    """PublicEvidence[] — hidden items are never listed; ``examined_detail`` only once examined."""
    out = []
    for ev in all_evidence(case):
        st = world["evidence"].get(ev["id"])
        if st is None or not _was_visible(ev, st):
            continue
        out.append(public_evidence_item(ev, st))
    return out


# ----------------------------------------------------------------------------- framing actions

def evaluate_framing_actions(case: dict, world: dict, rng: random.Random) -> list[dict[str, Any]]:
    """PLAN §8.8: for every suspect, every action not yet fired: if the trigger holds and rng.random() < probability,
    apply the effect and record it. Returns ``[{suspect_id, action_id, ticker, evidence, effect}]``.
    The RNG is consulted only when a trigger holds, so a seeded RNG gives reproducible outcomes."""
    game = world["game"]
    fired_list = game.setdefault("fired_framing_actions", [])
    fired_set = set(fired_list)
    index = evidence_index(case)
    dynamic = dynamic_evidence_ids(case)
    results: list[dict[str, Any]] = []
    for suspect in case.get("suspects", []):
        sid = suspect["id"]
        ctx = None
        for action in suspect.get("framing_actions", []) or []:
            action_id = action["id"]
            key = f"{sid}:{action_id}"
            if action_id in fired_set or key in fired_set:
                continue
            if ctx is None:
                ctx = conditions.context_for(case, world, sid)
            if not conditions.evaluate(action.get("trigger", ""), ctx):
                continue
            probability = float(action.get("probability", 1.0))
            if rng.random() >= probability:
                continue
            effect = action.get("effect") or {}
            added_public = None
            removed = effect.get("remove_evidence")
            if removed and removed in world["evidence"]:
                st = world["evidence"][removed]
                if st.get("state") in ("known", "examined"):
                    st["was_known"] = True
                st["state"] = "destroyed"
            added = effect.get("add_evidence_id")
            if added and added in index and added in dynamic:
                st = world["evidence"].setdefault(added, {"state": "hidden", "examined_turn": None})
                if st.get("state") == "hidden":
                    st["state"] = "known"
                added_public = public_evidence_item(index[added], st)
            fired_list.append(action_id)
            fired_set.add(action_id)
            results.append({
                "suspect_id": sid,
                "action_id": action_id,
                "ticker": action.get("ticker", ""),
                "evidence": added_public,
                "effect": {"remove_evidence": removed, "add_evidence_id": added},
            })
    return results
