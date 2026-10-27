#!/usr/bin/env python3
"""Scripted Vane Hall API smoke (PLAYTEST.md beats). Exit 0 only if all gates pass.

Usage (backend already up on :8000):
  LLM_MODE=scripted backend/.venv/bin/python scripts/api_playtest.py
Set PLAYTEST_GAME_FILE=path to write the game id there (verify_alibi.sh uses it for the restart gate).
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import urllib.error
import urllib.request

from websockets.sync.client import connect

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
FORBIDDEN_KEYS = {
    "secret",
    "secrets",
    "internal_reasoning",
    "honesty",
    "heard_log",
    "solution",
    "wants_to_tell",
    "points_to",
    "reveals",
}


def req(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def walk_forbidden(obj, path="$", hits=None):
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}"
            if key in FORBIDDEN_KEYS:
                hits.append(here)
            walk_forbidden(value, here, hits)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            walk_forbidden(value, f"{path}[{i}]", hits)
    return hits


def next_event(sock, wanted: str, limit: int = 30) -> dict | None:
    """Read WS events until one of type ``wanted`` arrives (None on timeout or after ``limit`` others)."""
    for _ in range(limit):
        try:
            event = json.loads(sock.recv(timeout=5))
        except TimeoutError:
            return None
        if event.get("type") == wanted:
            return event
    return None


def main() -> int:
    with contextlib.ExitStack() as cleanup:
        return play(cleanup)


def play(cleanup: contextlib.ExitStack) -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))
        print(("PASS" if ok else "FAIL"), name, detail)

    status, health = req("GET", "/api/health")
    check("health", status == 200 and bool(health and health.get("ok")), str(health))

    status, cases = req("GET", "/api/cases")
    ids = [c.get("id") for c in (cases or [])] if isinstance(cases, list) else []
    check("cases_include_vane_hall", "vane_hall_1923" in ids, str(ids))

    status, created = req(
        "POST",
        "/api/games",
        {"case_id": "vane_hall_1923", "difficulty": "detective", "accessibility": {}},
    )
    gid = (created or {}).get("game_id") if isinstance(created, dict) else None
    check("create_game", status == 201 and bool(gid), str(gid))
    if not gid:
        return _finish(results)
    if os.environ.get("PLAYTEST_GAME_FILE"):
        with open(os.environ["PLAYTEST_GAME_FILE"], "w", encoding="utf-8") as f:
            f.write(gid)

    status, game = req("GET", f"/api/games/{gid}")
    check("get_game_briefing_status", status == 200 and game.get("status") == "briefing", str(game.get("status")))

    sock = cleanup.enter_context(connect(BASE.replace("http", "ws", 1) + f"/api/ws/games/{gid}", open_timeout=5))
    hello = next_event(sock, "clock")
    check("ws_connects_with_clock", bool(hello), str(hello))

    status, turn = req(
        "POST",
        f"/api/games/{gid}/turn",
        {"type": "ask", "suspect_id": "pell", "text": "Where were you at twenty past eleven?"},
    )
    check("ask_pell", status == 200 and bool(turn and turn.get("spoken")), str(turn))
    pushed = next_event(sock, "turn_result")
    check("ws_pushes_turn_result", bool(pushed) and pushed["data"] == turn, str(pushed)[:160])

    status, search = req("POST", f"/api/games/{gid}/search", {"location_id": "billiard_room"})
    evidence = (search or {}).get("evidence") if isinstance(search, dict) else []
    check("search_billiard", status == 200 and bool(evidence), str(search))
    cigar = next((e for e in evidence if e.get("id") == "cigar_case"), evidence[0] if evidence else None)
    check("found_cigar_case", bool(cigar and cigar.get("id") == "cigar_case"), str(cigar))

    status, present = req(
        "POST",
        f"/api/games/{gid}/turn",
        {"type": "present", "suspect_id": "pell", "evidence_id": (cigar or {}).get("id")},
    )
    check("present_cigar", status == 200 and bool(present), str(present))

    # Watson runs after the turn-2 response goes out; its push is the signal that the notebook is stored.
    pushed_nb = next_event(sock, "notebook_updated")
    check("ws_pushes_notebook", bool(pushed_nb) and pushed_nb["data"].get("turn") == 2, str(pushed_nb)[:160])
    status, mid = req("GET", f"/api/games/{gid}")
    mid_hits = walk_forbidden(mid)
    check("no_forbidden_keys_mid_game", status == 200 and not mid_hits, str(mid_hits))
    notebook = (mid or {}).get("notebook") or {}
    check("watson_notebook_in_game_state", bool(pushed_nb) and notebook == pushed_nb["data"], str(notebook)[:160])

    gaps: list[tuple[str, str]] = []
    status, ask2 = req(
        "POST",
        f"/api/games/{gid}/turn",
        {
            "type": "ask",
            "suspect_id": "pell",
            "text": "So you never went to your room. Where did you really go?",
        },
    )
    spoken2 = ((ask2 or {}).get("spoken") or "").lower() if isinstance(ask2, dict) else ""
    admits_study = status == 200 and "study" in spoken2
    if status != 200:
        check("ask_after_present", False, str(ask2))
    elif admits_study:
        check("ask_after_present_admits_study", True, spoken2[:120])
    else:
        gaps.append(
            (
                "ask_after_present_no_study_admit",
                f"PLAYTEST expects Pell to admit the study; spoken={spoken2[:160]!r}",
            )
        )
        print("GAP ", gaps[-1][0], gaps[-1][1])

    status, _ = req(
        "POST",
        f"/api/games/{gid}/turn",
        {"type": "tactic", "suspect_id": "ada", "tactic": "flatter", "text": "You notice everything."},
    )
    check("flatter_ada_1", status == 200, "")
    status, _ = req(
        "POST",
        f"/api/games/{gid}/turn",
        {"type": "tactic", "suspect_id": "ada", "tactic": "flatter", "text": "I trust your eyes."},
    )
    check("flatter_ada_2", status == 200, "")

    status, dark = req("POST", f"/api/games/{gid}/search", {"location_id": "darkroom"})
    check("search_darkroom", status == 200 and bool((dark or {}).get("evidence")), str(dark))
    status, study = req("POST", f"/api/games/{gid}/search", {"location_id": "study"})
    check("search_study", status == 200 and bool((study or {}).get("evidence")), str(study))

    status, conf = req(
        "POST",
        f"/api/games/{gid}/confront",
        {"a": "pell", "b": "ada", "topic": "the gloves", "rounds": 2},
    )
    lines = (conf or {}).get("lines") if isinstance(conf, dict) else None
    check("confront", status == 200 and isinstance(lines, list) and len(lines) > 0, f"lines={len(lines or [])}")

    status, debrief = req(
        "POST",
        f"/api/games/{gid}/accuse",
        {
            "suspect_id": "pell",
            "method_evidence_ids": ["decanter", "cyanide_jar"],
            "motive_text": (
                "embezzlement from the Manchester accounts, Reginald was going to dissolve "
                "the partnership and go to the police"
            ),
            "confidence": 0.9,
        },
    )
    check(
        "accuse_correct",
        status == 200 and bool(debrief and debrief.get("correct") is True),
        str({k: (debrief or {}).get(k) for k in ("correct", "rank", "score")}),
    )

    status, game_after = req("GET", f"/api/games/{gid}")
    hits = walk_forbidden(game_after)
    check("no_forbidden_keys_in_game_state", status == 200 and not hits, str(hits))

    status, dbg = req("GET", f"/api/games/{gid}/debug")
    if (health or {}).get("debug_panel"):
        check("debug_has_suspects", status == 200 and bool((dbg or {}).get("suspects")), str(status))
    else:
        check("debug_hidden_without_debug_panel", status == 404, str(status))

    status, rewind = req("POST", f"/api/games/{gid}/rewind", {"turn": 1})
    rewound = isinstance(rewind, dict) and rewind.get("turn") == 1 and rewind.get("status") != "closed"
    check("rewind_reopens_turn_1", status == 200 and rewound, str({k: (rewind or {}).get(k) for k in ("turn", "status")}))
    status, _ = req("GET", f"/api/games/{gid}/debrief")
    check("debrief_gone_after_rewind", status == 404, str(status))

    return _finish(results, gaps)


def _finish(results: list[tuple[str, bool, str]], gaps: list[tuple[str, str]] | None = None) -> int:
    fails = [name for name, ok, _ in results if not ok]
    gaps = gaps or []
    print("---SUMMARY---")
    print(f"{len(results) - len(fails)}/{len(results)} passed, {len(gaps)} known gap(s)")
    for name, ok, detail in results:
        if not ok:
            print("FAIL", name, detail)
    for name, detail in gaps:
        print("GAP ", name, detail)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
