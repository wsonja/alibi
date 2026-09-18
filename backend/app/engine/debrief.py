"""Debrief: reveal reel, rumor map, what-you-missed, stats (PLAN §9 Debrief shape, §13; INTERFACES §6 additions)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from . import scoring
from . import stress as stress_mod
from . import world as world_mod
from .public import public_turn

__all__ = ["PLAYER_TURN_TYPES", "SPOKEN_TURN_TYPES", "build"]

SPOKEN_TURN_TYPES = ("ask", "tactic", "present", "confront")
PLAYER_TURN_TYPES = ("ask", "tactic", "present", "confront", "search", "accuse")


def _sorted_rows(turn_rows: list[dict]) -> list[dict]:
    rows = [r for r in (turn_rows or []) if isinstance(r, dict) and not r.get("archived")]
    return sorted(rows, key=lambda r: (int(r.get("turn") or 0), int(r.get("seq") or 0)))


def _guard_index(guard_rows: list[dict]) -> dict[tuple[int, str], list[dict]]:
    index: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for g in guard_rows or []:
        if not isinstance(g, dict):
            continue
        index[(int(g.get("turn") or 0), str(g.get("suspect_id")))].append(g)
    return index


def _guard_seq(g: dict) -> int | None:
    seq = g.get("seq")
    if seq is None and isinstance(g.get("detail"), dict):
        seq = g["detail"].get("seq")
    return int(seq) if seq is not None else None


def _row_clock(row: dict, fallback_minutes: int) -> str:
    clock = row.get("clock")
    if isinstance(clock, str) and clock:
        return clock
    snap = row.get("snapshot")
    if isinstance(snap, dict):
        minutes = (snap.get("game") or {}).get("clock_minutes")
        if minutes is not None:
            return world_mod.clock_str(minutes)
    return world_mod.clock_str(fallback_minutes)


def _reel(case: dict, rows: list[dict], guard_index: dict) -> list[dict]:
    suspects = {s["id"]: s for s in case.get("suspects", [])}
    reel: list[dict] = []
    for r in rows:
        actor = r.get("actor")
        if actor not in suspects or r.get("type") not in SPOKEN_TURN_TYPES:
            continue
        out = r.get("output") or {}
        inp = r.get("input") or {}
        turn, seq = int(r.get("turn") or 0), int(r.get("seq") or 0)
        events = [g for g in guard_index.get((turn, actor), []) if _guard_seq(g) in (None, seq)]
        detective_text = inp.get("detective_text")
        if detective_text is None:
            detective_text = inp.get("user_message")
        reel.append({
            "turn": turn,
            "seq": seq,
            "suspect_id": actor,
            "type": r.get("type"),
            "target": r.get("target"),
            "detective_text": detective_text,
            "spoken": out.get("spoken", ""),
            "internal_reasoning": out.get("internal_reasoning", ""),
            "honesty": out.get("honesty", "evasive"),
            "emotion": out.get("emotion", "neutral"),
            "tell": out.get("tell", ""),
            "stress_before": r.get("stress_before"),
            "stress_after": r.get("stress_after"),
            "reveals": list(out.get("reveals") or []),
            "accuses": out.get("accuses"),
            "guard_events": [{"kind": g.get("kind"), "detail": g.get("detail")} for g in events],
        })
    return reel


def _rumor_map(rows: list[dict]) -> list[dict]:
    edges: list[dict] = []
    for r in rows:
        out = r.get("output") or {}
        if r.get("type") == "offscreen":
            for d in out.get("deliveries") or []:
                edges.append({"from": d.get("from"), "to": d.get("to"), "text": d.get("text", ""),
                              "turn": int(d.get("turn") if d.get("turn") is not None else r.get("turn") or 0),
                              "channel": d.get("channel", "private")})
        elif r.get("type") == "confront" and out.get("accuses") and r.get("actor") != "detective":
            edges.append({"from": r.get("actor"), "to": r.get("target"), "text": out.get("spoken", ""),
                          "turn": int(r.get("turn") or 0), "channel": "confrontation", "accuses": out.get("accuses")})
    return edges


def _near_cracks(case: dict, world: dict, rows: list[dict]) -> list[dict]:
    suspects = {s["id"]: s for s in case.get("suspects", [])}
    revealed_final: set[str] = set()
    for st in world.get("suspects", {}).values():
        revealed_final.update(st.get("revealed_secret_ids", []))
    best: dict[tuple[str, str], dict] = {}

    def consider(entries: list[dict], turn: int) -> None:
        for e in entries:
            key = (e["suspect_id"], e["secret_id"])
            if e["secret_id"] in revealed_final:
                continue
            current = best.get(key)
            if current is None or e["stress"] > current["stress"]:
                best[key] = {"suspect_id": e["suspect_id"], "turn": turn, "stress": e["stress"],
                             "threshold": e["threshold"], "secret_id": e["secret_id"]}

    for r in rows:
        snap = r.get("snapshot")
        if isinstance(snap, dict) and snap.get("suspects"):
            consider(stress_mod.near_cracks(case, snap), int(r.get("turn") or 0))
    consider(stress_mod.near_cracks(case, world), int(world.get("game", {}).get("turn", 0)))

    out = []
    for (sid, secret_id), entry in best.items():
        secret = next((s for s in suspects.get(sid, {}).get("secrets", []) if s["id"] == secret_id), {})
        entry = dict(entry)
        entry["suspect_name"] = suspects.get(sid, {}).get("name", sid)
        entry["text"] = secret.get("text", "")
        entry["tier"] = secret.get("tier")
        out.append(entry)
    out.sort(key=lambda e: (e["turn"], e["suspect_id"], e["secret_id"]))
    return out


def _missed(case: dict, world: dict, rows: list[dict]) -> dict:
    dynamic = world_mod.dynamic_evidence_ids(case)
    never_examined: list[dict] = []
    for ev in world_mod.all_evidence(case):
        st = world.get("evidence", {}).get(ev["id"]) or {}
        state = st.get("state", "hidden")
        if state == "examined":
            continue
        if ev["id"] in dynamic and state == "hidden":
            continue  # never entered the world
        never_examined.append({"id": ev["id"], "name": ev.get("name", ev["id"]), "location": ev.get("location"),
                               "description": ev.get("description", ""), "state": state})

    never_revealed: list[dict] = []
    for suspect in case.get("suspects", []):
        st = world.get("suspects", {}).get(suspect["id"]) or {}
        revealed = set(st.get("revealed_secret_ids", []))
        unlocked = set(st.get("unlocked_secret_ids", []))
        for secret in suspect.get("secrets", []):
            if secret["id"] in revealed:
                continue
            never_revealed.append({"suspect_id": suspect["id"], "suspect_name": suspect.get("name", suspect["id"]),
                                   "secret_id": secret["id"], "tier": secret.get("tier"), "text": secret.get("text", ""),
                                   "unlocked": secret["id"] in unlocked})

    never_learned: list[dict] = []
    for r in rows:
        if r.get("type") != "offscreen":
            continue
        for d in (r.get("output") or {}).get("dropped") or []:
            never_learned.append({"from": d.get("from"), "to": d.get("to"), "text": d.get("text", ""),
                                  "turn": d.get("turn", r.get("turn")), "reason": "dropped"})
    for sid, st in world.get("suspects", {}).items():
        for item in st.get("outbox", []) or []:
            never_learned.append({"from": sid, "to": item.get("to"), "text": item.get("text", ""),
                                  "turn": item.get("queued_turn"), "reason": "never_delivered"})

    return {
        "evidence_never_examined": never_examined,
        "secrets_never_revealed": never_revealed,
        "near_cracks": _near_cracks(case, world, rows),
        "messages_never_learned": never_learned,
    }


def _stats(case: dict, world: dict) -> dict:
    game = world.get("game", {})
    dynamic = world_mod.dynamic_evidence_ids(case)
    total = 0
    examined = 0
    for ev in world_mod.all_evidence(case):
        st = world.get("evidence", {}).get(ev["id"]) or {}
        if ev["id"] in dynamic and st.get("state", "hidden") == "hidden":
            continue
        total += 1
        if st.get("state") == "examined":
            examined += 1
    samples = [float(x) for x in game.get("composure_samples", []) or []]
    return {
        "turns": int(game.get("turn", 0)),
        "clock": world_mod.clock_str(game.get("clock_minutes", 0)),
        "evidence_pct": round(100 * examined / total) if total else 0,
        "tactics_used": dict(game.get("tactics_used", {}) or {}),
        "composure_avg": round(sum(samples) / len(samples), 3) if samples else None,
    }


def _public_turns(case: dict, world: dict, rows: list[dict]) -> list[dict]:
    suspects = {s["id"]: s for s in case.get("suspects", [])}
    fallback_minutes = int(world.get("game", {}).get("clock_minutes", 0))
    turns: list[dict] = []
    for r in rows:
        ttype = r.get("type")
        if ttype not in PLAYER_TURN_TYPES:
            continue
        out = r.get("output") or {}
        inp = r.get("input") or {}
        actor = r.get("actor")
        kwargs: dict[str, Any] = {}
        if actor in suspects:
            state = {"stress": r.get("stress_after") or 0}
            kwargs.update(spoken=out.get("spoken"), tell=out.get("tell"), emotion=out.get("emotion"),
                          stress_pct=stress_mod.stress_pct(suspects[actor], state))
            if ttype == "confront":
                kwargs["other"] = r.get("target")
        turns.append(public_turn(
            turn=int(r.get("turn") or 0), seq=int(r.get("seq") or 0), type=ttype, actor=actor or "detective",
            target=r.get("target"), clock=_row_clock(r, fallback_minutes), detective_text=inp.get("detective_text"),
            tactic=inp.get("tactic"), evidence_id=inp.get("evidence_id"), **kwargs))
    return turns


def build(case: dict, world: dict, turn_rows: list[dict], guard_rows: list[dict], accusation: dict,
          cast_public: list[dict], *, game_id: str | None = None) -> dict:
    """Assemble the Debrief from persisted rows plus the final world and the accusation record."""
    accusation = accusation or {}
    solution = case.get("solution") or {}
    suspects = {s["id"]: s for s in case.get("suspects", [])}
    rows = _sorted_rows(turn_rows)
    guard_index = _guard_index(guard_rows)

    score = accusation.get("score")
    if not isinstance(score, dict):
        score = scoring.score(case, accusation.get("suspect_id"), accusation.get("method_evidence_ids") or [],
                              accusation.get("motive_points", 0))
    total = int(score.get("total", 0))
    correct = accusation.get("correct")
    if correct is None:
        correct = accusation.get("suspect_id") == solution.get("murderer")
    murderer = solution.get("murderer")

    return {
        "game_id": game_id if game_id is not None else accusation.get("game_id"),
        "case_title": case.get("title", ""),
        "correct": bool(correct),
        "accused": accusation.get("suspect_id"),
        "accused_name": suspects.get(accusation.get("suspect_id"), {}).get("name"),
        "score": {"murderer": int(score.get("murderer", 0)), "method": int(score.get("method", 0)),
                  "motive": int(score.get("motive", 0)), "total": total},
        "rank": accusation.get("rank") or scoring.rank(total),
        "confidence": accusation.get("confidence"),
        "confidence_badge": accusation.get("confidence_badge", scoring.confidence_badge(accusation.get("confidence"))),
        "motive_text": accusation.get("motive_text", ""),
        "motive_note": accusation.get("motive_note"),
        "truth": {
            "murderer": murderer,
            "murderer_name": suspects.get(murderer, {}).get("name", murderer),
            "method": solution.get("method", ""),
            "motive": solution.get("motive", ""),
            "method_evidence_ids": list(solution.get("method_evidence_ids") or []),
            "motive_evidence_ids": list(solution.get("motive_evidence_ids") or []),
            "timeline_truth": list(case.get("timeline_truth") or []),
            "red_herrings": list(case.get("red_herrings") or []),
            "cause_of_death_truth": (case.get("victim") or {}).get("cause_of_death_truth", ""),
        },
        "reel": _reel(case, rows, guard_index),
        "rumor_map": _rumor_map(rows),
        "missed": _missed(case, world, rows),
        "stats": _stats(case, world),
        "cast": list(cast_public or []),
        "turns": _public_turns(case, world, rows),
    }
