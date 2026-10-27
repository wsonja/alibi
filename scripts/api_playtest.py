#!/usr/bin/env python3
"""Scripted Vane Hall API smoke (PLAYTEST.md beats). Exit 0 only if all gates pass.

Usage (backend already up on :8000):
  LLM_MODE=scripted backend/.venv/bin/python scripts/api_playtest.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
FORBIDDEN_KEYS = {
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


def main() -> int:
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

    status, game = req("GET", f"/api/games/{gid}")
    check("get_game_briefing_status", status == 200 and game.get("status") == "briefing", str(game.get("status")))

    status, turn = req(
        "POST",
        f"/api/games/{gid}/turn",
        {"type": "ask", "suspect_id": "pell", "text": "Where were you at twenty past eleven?"},
    )
    check("ask_pell", status == 200 and bool(turn and turn.get("spoken")), str(turn))

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
    check("debug_has_suspects", status == 200 and bool((dbg or {}).get("suspects")), "")

    status, rewind = req("POST", f"/api/games/{gid}/rewind", {"turn": 1})
    # Temporary API documents 501 until the real backend lands.
    check("rewind_documented", status in (200, 501), str(rewind))

    return _finish(results)


def _finish(results: list[tuple[str, bool, str]]) -> int:
    fails = [name for name, ok, _ in results if not ok]
    print("---SUMMARY---")
    print(f"{len(results) - len(fails)}/{len(results)} passed")
    for name, ok, detail in results:
        if not ok:
            print("FAIL", name, detail)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
