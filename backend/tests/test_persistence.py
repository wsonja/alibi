"""PLAN §2.5: every turn is in the DB before the response, and a restarted server resumes exactly.

A second app on the same SQLite file is a restarted server: it shares nothing with the first except the DB.
"""
import shutil

CASE = "vane_hall_1923"


def ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json()


def play(c, gid, moves):
    out = []
    for path, body in moves:
        out.append(ok(c.post(f"/api/games/{gid}/{path}", json=body)))
    return out


OPENING = [
    ("turn", {"type": "ask", "suspect_id": "pell", "text": "Where were you after dinner?"}),
    ("search", {"location_id": "study"}),
    ("turn", {"type": "present", "suspect_id": "margaret", "evidence_id": "decanter"}),
]
MIDGAME = [
    ("confront", {"a": "crane", "b": "margaret", "topic": "the telephone call"}),
    ("turn", {"type": "tactic", "suspect_id": "ada", "tactic": "threaten"}),
    ("turn", {"type": "ask", "suspect_id": "crane", "text": "Who rang the house at ten?"}),
    ("search", {"location_id": "garden"}),
    ("turn", {"type": "ask", "suspect_id": "margaret", "text": "Where were you at ten?"}),
]


def test_every_response_is_already_in_the_db(make_api):
    with make_api() as live:
        gid = ok(live.post("/api/games", json={"case_id": CASE}), 201)["game_id"]
        play(live, gid, OPENING)
        live_state = ok(live.get(f"/api/games/{gid}"))
        with make_api() as reader:
            assert ok(reader.get(f"/api/games/{gid}")) == live_state
            assert gid in {g["game_id"] for g in ok(reader.get("/api/games"))}


def test_a_restarted_server_plays_on_exactly_like_one_that_never_stopped(make_api, tmp_path):
    copy_url = f"sqlite+aiosqlite:///{tmp_path / 'copy.db'}"
    with make_api(debug_panel=True) as running:
        # Inspector ticks every 2 turns, so the resumed half draws a random ticker three times.
        gid = ok(running.post("/api/games", json={"case_id": CASE, "difficulty": "inspector"}), 201)["game_id"]
        play(running, gid, OPENING)
        shutil.copy(tmp_path / "alibi.db", tmp_path / "copy.db")
        uninterrupted = play(running, gid, MIDGAME)
        uninterrupted_state = ok(running.get(f"/api/games/{gid}"))
        uninterrupted_debug = ok(running.get(f"/api/games/{gid}/debug"))

    with make_api(debug_panel=True, database_url=copy_url) as restarted:
        resumed = play(restarted, gid, MIDGAME)
        resumed_state = ok(restarted.get(f"/api/games/{gid}"))
        resumed_debug = ok(restarted.get(f"/api/games/{gid}/debug"))

    assert resumed == uninterrupted
    assert resumed_state == uninterrupted_state
    assert resumed_debug == uninterrupted_debug
    assert resumed_state["turn"] == 8 and resumed_state["notebook"]["turn"] == 8


def test_a_rewind_survives_a_restart(make_api):
    with make_api() as c:
        gid = ok(c.post("/api/games", json={"case_id": CASE}), 201)["game_id"]
        play(c, gid, OPENING)
        rewound = ok(c.post(f"/api/games/{gid}/rewind", json={"turn": 1}))
    with make_api() as c:
        assert ok(c.get(f"/api/games/{gid}")) == rewound
        nxt = play(c, gid, OPENING[1:2])[0]
    assert rewound["turn"] == 1 and nxt["clock"]


def test_a_closed_case_reopens_on_its_debrief_after_a_restart(make_api):
    with make_api() as c:
        gid = ok(c.post("/api/games", json={"case_id": CASE}), 201)["game_id"]
        play(c, gid, OPENING)
        debrief = ok(c.post(f"/api/games/{gid}/accuse", json={"suspect_id": "pell", "method_evidence_ids": ["decanter"]}))
    with make_api() as c:
        assert ok(c.get(f"/api/games/{gid}/debrief")) == debrief
        assert ok(c.get(f"/api/games/{gid}"))["status"] == "closed"
        summary = next(g for g in ok(c.get("/api/games")) if g["game_id"] == gid)
    assert (summary["correct"], summary["rank"]) == (debrief["correct"], debrief["rank"])
