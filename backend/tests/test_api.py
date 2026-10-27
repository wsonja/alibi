"""The HTTP and WebSocket contract (PLAN §9, docs/INTERFACES.md §6) on the real app in scripted mode."""
import queue
import threading

from app.engine.public import forbidden_keys_present

CASE = "vane_hall_1923"
SUSPECTS = {"margaret", "crane", "pell", "ada"}
# PLAN §9: a closed game's Debrief shows private reasoning; its near-cracks show raw stress beside the thresholds.
DEBRIEF_MAY_SHOW = {"internal_reasoning", "honesty", "reveals", "stress"}


def ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json()


def new_game(c, **body):
    return ok(c.post("/api/games", json={"case_id": CASE, **body}), 201)["game_id"]


def ask(c, gid, sid, text):
    return ok(c.post(f"/api/games/{gid}/turn", json={"type": "ask", "suspect_id": sid, "text": text}))


def receive(ws, timeout=5.0):
    """ws.receive_json without a hang: a missing event fails the test instead of blocking it."""
    box: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: box.put(ws.receive_json()), daemon=True).start()
    return box.get(timeout=timeout)


def test_health_reports_mode_and_loaded_cases(make_api):
    with make_api() as c:
        h = ok(c.get("/api/health"))
    assert h["ok"] is True and h["llm_mode"] == "scripted" and h["debug_panel"] is False
    assert h["cases"] >= 1 and set(h["models"]) == {"suspect", "author", "guard"}


def test_a_whole_game_never_sends_private_keys_before_the_debrief(make_api):
    bodies = []

    def keep(r, status=200):
        bodies.append(ok(r, status))
        return bodies[-1]

    with make_api() as c:
        keep(c.get("/api/cases"))
        gid = keep(c.post("/api/games", json={"case_id": CASE}), 201)["game_id"]
        keep(c.post(f"/api/games/{gid}/turn", json={"type": "ask", "suspect_id": "pell", "text": "Where were you?"}))
        keep(c.post(f"/api/games/{gid}/turn", json={"type": "tactic", "suspect_id": "ada", "tactic": "flatter"}))
        keep(c.post(f"/api/games/{gid}/search", json={"location_id": "study"}))
        keep(c.post(f"/api/games/{gid}/turn",
                    json={"type": "present", "suspect_id": "margaret", "evidence_id": "decanter"}))
        keep(c.post(f"/api/games/{gid}/confront",
                    json={"a": "crane", "b": "margaret", "topic": "the telephone call", "interject": "Who rang?"}))
        keep(c.post(f"/api/games/{gid}/confront/interject", json={"text": "Answer him."}))
        keep(c.get(f"/api/games/{gid}"))
        keep(c.get("/api/games"))
        assert c.get(f"/api/games/{gid}/debrief").status_code == 404
        debrief = ok(c.post(f"/api/games/{gid}/accuse", json={
            "suspect_id": "pell", "method_evidence_ids": ["decanter"], "motive_text": "money", "confidence": 0.8}))
        assert ok(c.get(f"/api/games/{gid}/debrief")) == debrief
        closed = keep(c.get(f"/api/games/{gid}"))

    for body in bodies:
        assert forbidden_keys_present(body) == []
    assert closed["status"] == "closed"
    assert set(forbidden_keys_present(debrief)) <= DEBRIEF_MAY_SHOW
    assert debrief["truth"]["murderer"] in SUSPECTS


def test_debug_and_case_export_exist_only_with_debug_panel(make_api):
    with make_api() as c:
        gid = new_game(c)
        ask(c, gid, "pell", "Where were you after dinner?")
        assert c.get(f"/api/games/{gid}/debug").status_code == 404
        assert c.get(f"/api/cases/{CASE}/export").status_code == 404
    with make_api(debug_panel=True) as c:
        debug = ok(c.get(f"/api/games/{gid}/debug"))
        exported = ok(c.get(f"/api/cases/{CASE}/export"))
        assert ok(c.get("/api/health"))["debug_panel"] is True
    assert set(debug["suspects"]) == SUSPECTS and debug["turn"] == 1
    assert debug["cross_contamination"] == []
    assert exported["id"] == CASE and exported["solution"]["murderer"] in SUSPECTS


def test_cross_contamination_flags_another_suspects_secret_inside_a_prompt(case, world):
    from app.services.game_service import cross_contamination

    secret = next(s for s in case["suspects"] if s["id"] == "pell")["secrets"][0]
    assert cross_contamination(case, world) == []
    world["suspects"]["ada"]["last_system_blocks"] = [f"You are Ada Finch. {secret['text']}"]
    assert cross_contamination(case, world) == [{"suspect_id": "ada", "found": f"pell:{secret['id']}"}]


def test_watson_writes_the_notebook_after_every_second_turn_from_what_was_said(make_api):
    with make_api() as c:
        gid = new_game(c)
        ask(c, gid, "pell", "Where were you after dinner?")
        assert ok(c.get(f"/api/games/{gid}"))["notebook"] is None
        ask(c, gid, "ada", "Where were you at a quarter past ten?")
        state = ok(c.get(f"/api/games/{gid}"))

    notebook = state["notebook"]
    spoken = " ".join(t.get("spoken") or "" for t in state["turns"])
    assert notebook["turn"] == 2
    assert {s["id"] for s in notebook["per_suspect"]} <= SUSPECTS
    claims = [cl for s in notebook["per_suspect"] for cl in s["claims"]]
    assert claims and all(cl["quote"] in spoken for cl in claims)


def test_websocket_pushes_turn_clock_and_notebook_events(make_api):
    with make_api() as c:
        gid = new_game(c)
        with c.websocket_connect(f"/api/ws/games/{gid}") as ws:
            assert receive(ws)["type"] == "clock"
            first = ask(c, gid, "pell", "Where were you after dinner?")
            ask(c, gid, "ada", "Where were you at a quarter past ten?")
            events = []
            while not events or events[-1]["type"] != "notebook_updated":
                events.append(receive(ws))
        state = ok(c.get(f"/api/games/{gid}"))

    types = [e["type"] for e in events]
    assert events[0] == {"type": "turn_result", "data": first}
    assert types.count("turn_result") == 2 and "clock" in types
    assert events[-1]["data"] == state["notebook"]
    assert "guard_event" not in types
    assert all(forbidden_keys_present(e) == [] for e in events)


def test_websocket_streams_confrontation_lines(make_api):
    with make_api() as c:
        gid = new_game(c)
        with c.websocket_connect(f"/api/ws/games/{gid}") as ws:
            receive(ws)
            lines = ok(c.post(f"/api/games/{gid}/confront",
                              json={"a": "crane", "b": "margaret", "topic": "the telephone call", "rounds": 2}))["lines"]
            events = []
            while not events or events[-1]["type"] != "confront_done":
                events.append(receive(ws))

    assert [e["data"] for e in events if e["type"] == "confront_line"] == lines
    assert events[-1]["data"] == {"turn": 1}


def test_rewind_returns_to_an_earlier_turn_and_play_continues(make_api):
    with make_api() as c:
        gid = new_game(c)
        ask(c, gid, "pell", "Where were you after dinner?")
        after_one = ok(c.get(f"/api/games/{gid}"))
        ask(c, gid, "ada", "Where were you at a quarter past ten?")
        ok(c.post(f"/api/games/{gid}/accuse", json={"suspect_id": "ada"}))

        rewound = ok(c.post(f"/api/games/{gid}/rewind", json={"turn": 1}))
        assert c.get(f"/api/games/{gid}/debrief").status_code == 404
        again = ask(c, gid, "margaret", "Where were you at ten?")
        bad = c.post(f"/api/games/{gid}/rewind", json={"turn": 9})

    assert rewound == after_one
    assert again["turn"] == 2
    assert bad.status_code == 400 and "turn 9" in bad.json()["error"]


def test_retry_starts_a_fresh_game_on_the_same_case(make_api):
    with make_api() as c:
        gid = new_game(c, difficulty="inspector")
        ask(c, gid, "pell", "Where were you after dinner?")
        fresh = ok(c.post(f"/api/games/{gid}/retry"))["game_id"]
        state = ok(c.get(f"/api/games/{fresh}"))
    assert fresh != gid
    assert (state["case"]["id"], state["difficulty"], state["turn"]) == (CASE, "inspector", 0)


def test_import_accepts_a_valid_case_and_rejects_a_broken_one(make_api):
    with make_api(debug_panel=True) as c:
        exported = ok(c.get(f"/api/cases/{CASE}/export"))
        same = ok(c.post("/api/cases/import", json={"case": exported}))["case_id"]
        variant = ok(c.post("/api/cases/import", json={"case": {**exported, "title": "Vane Hall, Again"}}))["case_id"]
        listed = {x["id"] for x in ok(c.get("/api/cases"))}
        new_game(c, case_id=variant)
        broken = c.post("/api/cases/import", json={"case": {k: v for k, v in exported.items() if k != "suspects"}})

    assert same == CASE
    assert variant != CASE and variant in listed
    assert broken.status_code == 400 and broken.json()["error"]


def test_case_generation_is_refused_clearly_without_gemini(make_api):
    with make_api() as c:
        r = c.post("/api/cases/generate", json={"setting": "a lighthouse in a storm"})
        job = c.get("/api/cases/jobs/nope")
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["error"]
    assert job.status_code == 404


def test_api_key_is_saved_to_dotenv_and_switches_auto_mode_to_gemini(make_api, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text("LLM_MODE=auto\nGEMINI_API_KEY=\n")
    with make_api(llm_mode="auto", fake_llm=False) as c:
        assert ok(c.get("/api/health"))["llm_mode"] == "scripted"
        saved = c.post("/api/settings/api-key", json={"api_key": "AIzaTest-key_123"})
        mode = ok(c.get("/api/health"))["llm_mode"]
        bad = c.post("/api/settings/api-key", json={"api_key": "two words\nLLM_MODE=scripted"})

    assert ok(saved) == {"llm_mode": "gemini"} and mode == "gemini"
    assert dotenv.read_text().splitlines() == ["LLM_MODE=auto", "GEMINI_API_KEY=AIzaTest-key_123"]
    assert bad.status_code == 400 and "two words" not in bad.text


def test_gemini_mode_without_a_key_still_plays_every_turn(make_api, monkeypatch):
    from app.agents import client

    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(client, "_dotenv_loaded", True)
    with make_api(llm_mode="gemini", fake_llm=False) as c:
        assert ok(c.get("/api/health"))["llm_mode"] == "gemini"
        gid = new_game(c)
        first = ask(c, gid, "pell", "Where were you after dinner?")
        second = ask(c, gid, "ada", "Where were you at a quarter past ten?")
        notebook = ok(c.get(f"/api/games/{gid}"))["notebook"]
    assert first["spoken"] and second["spoken"]
    assert notebook["turn"] == 2


def test_errors_use_one_shape(make_api):
    with make_api() as c:
        gid = new_game(c)
        unknown_game = c.get("/api/games/nope")
        unknown_suspect = c.post(f"/api/games/{gid}/turn", json={"type": "ask", "suspect_id": "nobody", "text": "hi"})
        unknown_case = c.post("/api/games", json={"case_id": "nope"})
        malformed = c.post(f"/api/games/{gid}/turn", json={"type": "dance", "suspect_id": "pell"})
        socket_closed = c.websocket_connect("/api/ws/games/nope")
        with socket_closed as ws:
            closed = ws.receive()

    assert [r.status_code for r in (unknown_game, unknown_suspect, unknown_case, malformed)] == [404, 400, 404, 422]
    assert all(isinstance(r.json()["error"], str) for r in (unknown_game, unknown_suspect, unknown_case, malformed))
    assert closed["type"] == "websocket.close" and closed["code"] == 4404
