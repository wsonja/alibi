"""The Director end to end with a fake performer: a full Vane Hall game via proof path 1, context isolation,
the guard loop, LLM fallback, confrontations, framing plumbing, snapshots and the debrief."""
import copy
import json

import pytest

from app.engine import Director, GameClosed, debrief, forbidden_keys_present, snapshot
from app.engine import world as world_mod
from tests.conftest import FALLBACK_LINES, FakePerformer, InvalidOutput, LLMUnavailable


def assert_public(obj):
    assert forbidden_keys_present(obj) == [], forbidden_keys_present(obj)


def assert_isolated(case, contexts):
    """No PerformContext ever carries another suspect's secrets/knowledge/state, or the solution."""
    assert contexts, "the performer was never called"
    by_id = {s["id"]: s for s in case["suspects"]}
    for ctx in contexts:
        sid = ctx["suspect"]["id"]
        assert ctx["state"]["suspect_id"] == sid
        dump = json.dumps(ctx)
        assert "solution" not in ctx and "timeline_truth" not in ctx and '"solution"' not in dump
        assert case["solution"]["method"] not in dump and case["solution"]["motive"] not in dump
        for ev in case["timeline_truth"]:
            assert ev["event"] not in dump
        for other_id, other in by_id.items():
            if other_id == sid:
                continue
            for secret in other["secrets"]:
                assert secret["text"] not in dump, f"{sid} context contains {other_id}'s secret {secret['id']}"
            for fact in other["knowledge"]:
                assert fact not in dump, f"{sid} context contains {other_id}'s knowledge"
        assert set(ctx["suspect_ids"]) == set(by_id)
        assert ctx["cast_names"][sid] == by_id[sid]["name"]
        assert set(ctx["unlocked"]).isdisjoint(ctx["locked"])
        assert set(ctx["unlocked"]) | set(ctx["locked"]) == {s["id"] for s in by_id[sid]["secrets"]}


# ----------------------------------------------------------------------------- the full game

async def test_full_game_proof_path_one(case, make_director, fake_performer):
    d = make_director()
    world = d.world
    all_outcomes = []

    # 1. search the billiard room → cigar case examined
    out = d.search("billiard_room")
    all_outcomes.append(out)
    assert out["search"]["examined"] == ["cigar_case"]
    assert out["search"]["evidence"][0]["examined_detail"].startswith("Silver, monogrammed")
    assert world["game"]["turn"] == 1 and out["clock"] == "00:25"
    assert world["game"]["status"] == "investigating"
    assert out["watson_visible"]["examined_evidence"][0]["name"] == "Mr. Pell's cigar case"

    # 2. present the cigar case to Pell → pressure jumps, p1 unlocks (he still lies this turn: p1 was locked)
    out = await d.player_turn({"type": "present", "suspect_id": "pell", "evidence_id": "cigar_case",
                               "player_signal": {"composure": "confident", "gaze": "evidence"}})
    all_outcomes.append(out)
    pell = world["suspects"]["pell"]
    assert fake_performer.contexts[-1]["unlocked"] == [] and fake_performer.contexts[-1]["evidence"]["points_to_self"]
    assert fake_performer.contexts[-1]["user_message"].startswith("The detective shows you: Mr. Pell's cigar case. Silver")
    assert pell["stress"] == 5  # model 2 + evidence 4 = 6 → clamped to 5
    assert pell["unlocked_secret_ids"] == ["p1"] and pell["revealed_secret_ids"] == []
    assert out["private_turns"][0]["output"]["honesty"] == "lie"
    assert out["private_turns"][0]["stress_before"] == 0 and out["private_turns"][0]["stress_after"] == 5
    assert pell["last_seen_location"] == "billiard_room"
    assert world["game"]["composure_samples"] == [0.9]
    pub = out["public_turns"][0]
    assert pub["type"] == "present" and pub["evidence_id"] == "cigar_case" and pub["stress_pct"] == 36
    assert pub["clock"] == "00:30"

    # 3. ask him again → p1 revealed
    out = await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "So where did you really go for your cigars?"})
    all_outcomes.append(out)
    assert fake_performer.contexts[-1]["unlocked"] == ["p1"]
    assert fake_performer.contexts[-1]["user_message"] == "Detective: So where did you really go for your cigars?"
    assert out["private_turns"][0]["output"]["reveals"] == ["p1"]
    assert pell["revealed_secret_ids"] == ["p1"]
    assert out["public_turns"][0]["tell"] == case["suspects"][2]["tells"]["cracking"]
    assert out["offscreen"] is not None and world["game"]["turn"] == 3  # first tick: rumor seed goes out
    assert any(h["from"] == "pell" and h["channel"] == "private" for h in world["suspects"]["ada"]["heard_log"])

    # 4./5. flatter Ada twice → a3 unlockable
    ada = world["suspects"]["ada"]
    out = await d.player_turn({"type": "tactic", "tactic": "flatter", "suspect_id": "ada"})
    all_outcomes.append(out)
    assert fake_performer.contexts[-1]["user_message"] == "Detective (flatter): You strike me as the only sensible person in this house."
    assert out["public_turns"][0]["detective_text"] == "You strike me as the only sensible person in this house."
    assert ada["stress"] == 4 and ada["flatter_count"] == 1
    out = await d.player_turn({"type": "tactic", "tactic": "flatter", "suspect_id": "ada", "text": "You notice things."})
    all_outcomes.append(out)
    assert fake_performer.contexts[-1]["user_message"] == "Detective (flatter): You notice things."
    assert ada["stress"] == 8 and ada["flatter_count"] == 2
    assert ada["unlocked_secret_ids"] == ["a1", "a2", "a3"]
    assert pell["stress"] == 4  # decayed twice while not addressed (6 → 4); p1 stays unlocked
    assert pell["unlocked_secret_ids"] == ["p1"]

    # 6. ask Ada about the gloves → a3 revealed
    out = await d.player_turn({"type": "ask", "suspect_id": "ada", "text": "Did you see Mr. Pell with gloves?"})
    all_outcomes.append(out)
    assert out["private_turns"][0]["output"]["reveals"] == ["a3"]
    assert ada["revealed_secret_ids"] == ["a3"]
    assert world["game"]["turn"] == 6 and out["offscreen"] is not None

    # 7. search the darkroom → cigar ash + cyanide jar
    out = d.search("darkroom")
    all_outcomes.append(out)
    assert out["search"]["examined"] == ["cyanide_jar", "cigar_ash"]
    # p3 still locked: needs p2 revealed first
    assert "p3" not in pell["unlocked_secret_ids"]

    # 8. accuse Pell
    out = await d.accuse({"suspect_id": "pell", "method_evidence_ids": ["cyanide_jar", "decanter"],
                          "motive_text": "He was stealing from the firm.", "confidence": 0.9}, motive_points=0)
    all_outcomes.append(out)
    acc = out["accusation"]
    assert acc["score"] == {"murderer": 60, "method": 20, "motive": 0, "total": 80}
    assert acc["correct"] is True and acc["rank"] == "Detective" and acc["confidence_badge"] == "bold call"
    assert world["game"]["status"] == "closed" and world["game"]["turn"] == 8
    with pytest.raises(GameClosed):
        await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "Anything else?"})
    with pytest.raises(GameClosed):
        d.search("garden")

    # isolation + public hygiene across the whole game
    assert_isolated(case, fake_performer.contexts)
    for o in all_outcomes:
        assert_public(o["public_turns"])
        assert_public(o["world_events"])
        assert_public(o["tickers"])
        for row in o["private_turns"]:
            assert {"turn", "seq", "type", "actor", "target", "input", "output", "stress_before", "stress_after",
                    "latency_ms"} <= set(row)
    assert_public(d.cast_public())
    assert world["game"]["tactics_used"] == {"search": 2, "present": 1, "ask": 2, "flatter": 2}
    assert pell["last_system_blocks"] and "You are Thomas Pell" in pell["last_system_blocks"][0]
    assert all(isinstance(m["content"], str) for m in pell["conversation"])
    assert [m["role"] for m in pell["conversation"]] == ["user", "assistant"] * 2

    # snapshot round-trips and the debrief builds from the rows
    snap = snapshot.take(world)
    assert snap == world and snap is not world
    restored = snapshot.restore(json.loads(json.dumps(snap)))
    assert restored == world
    rows = [r for o in all_outcomes for r in o["private_turns"]]
    guards = [g for o in all_outcomes for g in o["guard_events"]]
    deb = debrief.build(case, world, rows, guards, acc, d.cast_public(), game_id="g1")
    assert deb["correct"] and deb["score"]["total"] == 80 and deb["rank"] == "Detective"
    assert deb["truth"]["murderer"] == "pell" and deb["truth"]["murderer_name"] == "Thomas Pell"
    assert deb["truth"]["timeline_truth"] == case["timeline_truth"]
    reel_ids = [(r["suspect_id"], r["turn"]) for r in deb["reel"]]
    assert reel_ids == [("pell", 2), ("pell", 3), ("ada", 4), ("ada", 5), ("ada", 6)]
    assert deb["reel"][1]["reveals"] == ["p1"] and deb["reel"][0]["honesty"] == "lie"
    assert all("internal_reasoning" in r for r in deb["reel"])
    assert any(e["from"] == "pell" and e["to"] == "ada" and e["channel"] == "private" for e in deb["rumor_map"])
    missed = deb["missed"]
    assert {e["id"] for e in missed["evidence_never_examined"]} == {"decanter", "solicitor_letter", "ledger", "necklace_clasp", "torn_reference"}
    assert ("pell", "p3") in {(s["suspect_id"], s["secret_id"]) for s in missed["secrets_never_revealed"]}
    assert not any(s["secret_id"] in ("p1", "a3") for s in missed["secrets_never_revealed"])
    assert deb["stats"]["turns"] == 8 and deb["stats"]["evidence_pct"] == 38 and deb["stats"]["composure_avg"] == 0.9
    assert deb["stats"]["clock"] == world_mod.clock_str(world["game"]["clock_minutes"])
    assert [t["type"] for t in deb["turns"]] == ["search", "present", "ask", "tactic", "tactic", "ask", "search", "accuse"]
    assert deb["game_id"] == "g1" and deb["case_title"] == case["title"]


# ----------------------------------------------------------------------------- guard loop (§7.4)

async def test_leak_guard_regenerates_then_falls_back(case, make_director, fake_performer):
    d = make_director()
    leaky = {"spoken": "Very well — I went to the study, Inspector.", "internal_reasoning": "slipped", "honesty": "truthful",
             "emotion": "afraid", "stress_delta": 1, "reveals": ["p1"], "accuses": None, "wants_to_tell": [], "tell": ""}
    fake_performer.queue = [leaky, leaky, leaky]
    out = await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "Where were you at twenty past?"})
    assert fake_performer.calls == 3
    kinds = [e["kind"] for e in out["guard_events"]]
    assert kinds.count("reveals_stripped") == 3  # p1 is locked: stripped every attempt
    assert kinds.count("leak_regenerated") == 2 and kinds[-1] == "leak_fallback"
    assert fake_performer.contexts[0]["retry_ids"] == []
    assert fake_performer.contexts[1]["retry_ids"] == ["p1"] and fake_performer.contexts[2]["retry_ids"] == ["p1"]
    clean = out["private_turns"][0]["output"]
    assert clean["spoken"] == FALLBACK_LINES["pell"] and clean["reveals"] == [] and clean["honesty"] == "evasive"
    assert out["public_turns"][0]["spoken"] == FALLBACK_LINES["pell"]
    assert d.world["suspects"]["pell"]["revealed_secret_ids"] == []
    assert d.world["suspects"]["pell"]["conversation"][-1]["content"] == FALLBACK_LINES["pell"]
    for e in out["guard_events"]:
        assert e["suspect_id"] == "pell" and e["turn"] == 1 and e["seq"] == 1


async def test_leak_guard_retry_succeeds(case, make_director, fake_performer):
    d = make_director()
    leaky = {"spoken": "I was in the study.", "honesty": "truthful", "emotion": "afraid", "stress_delta": 1,
             "reveals": [], "accuses": None, "wants_to_tell": [], "tell": "", "internal_reasoning": ""}
    fake_performer.queue = [leaky]  # second attempt falls through to the canned deflection
    out = await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "Where were you?"})
    assert fake_performer.calls == 2
    assert [e["kind"] for e in out["guard_events"]] == ["leak_regenerated"]
    assert out["public_turns"][0]["spoken"] == "I have nothing more to add on that subject."


async def test_guard_skipped_when_nothing_locked(case, make_director, fake_performer):
    calls = []

    async def guard(spoken, locked):
        calls.append(locked)
        return {"leaked": [], "reason": ""}

    d = make_director(guard=guard)
    pell = d.world["suspects"]["pell"]
    pell["unlocked_secret_ids"] = ["p1", "p2", "p3"]
    await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "Well?"})
    assert calls == []
    await d.player_turn({"type": "ask", "suspect_id": "ada", "text": "Well?"})
    assert len(calls) == 1 and [s["id"] for s in calls[0]] == ["a1", "a2", "a3"]
    assert all({"id", "text", "key_phrases"} == set(s) for s in calls[0])


async def test_empty_spoken_retries_once_then_fallback(case, make_director, fake_performer):
    d = make_director()
    empty = {"spoken": "   ", "honesty": "evasive", "emotion": "neutral", "stress_delta": 0, "reveals": [],
             "accuses": None, "wants_to_tell": [], "tell": "", "internal_reasoning": ""}
    fake_performer.queue = [empty, empty]
    out = await d.player_turn({"type": "ask", "suspect_id": "crane", "text": "Doctor?"})
    assert fake_performer.calls == 2
    assert [e["kind"] for e in out["guard_events"]] == ["invalid_output", "invalid_output"]
    assert out["public_turns"][0]["spoken"] == FALLBACK_LINES["crane"]


async def test_llm_unavailable_uses_fallback_performer(case, make_director, fake_performer):
    scripted = FakePerformer()
    d = make_director(fallback_performer=scripted)
    fake_performer.queue = [LLMUnavailable("503 everywhere")]
    out = await d.player_turn({"type": "ask", "suspect_id": "margaret", "text": "Were you really in bed with a headache?"})
    assert fake_performer.calls == 1 and scripted.calls == 1
    assert [e["kind"] for e in out["guard_events"]] == ["llm_fallback_scripted"]
    assert out["guard_events"][0]["detail"]["fallback_performer"] is True
    assert out["public_turns"][0]["spoken"] == case["suspects"][0]["secrets"][0]["cover_story"]  # m1 locked → cover
    assert_isolated(case, scripted.contexts)


async def test_llm_unavailable_without_fallback_performer_uses_line(case, make_director, fake_performer):
    d = make_director()
    fake_performer.queue = [LLMUnavailable("down")]
    out = await d.player_turn({"type": "ask", "suspect_id": "ada", "text": "Well?"})
    assert [e["kind"] for e in out["guard_events"]] == ["llm_fallback_scripted"]
    assert out["public_turns"][0]["spoken"] == FALLBACK_LINES["ada"]


async def test_invalid_output_retries_once(case, make_director, fake_performer):
    d = make_director()
    fake_performer.queue = [InvalidOutput("bad json")]
    out = await d.player_turn({"type": "ask", "suspect_id": "ada", "text": "Well?"})
    assert fake_performer.calls == 2
    assert out["guard_events"][0]["kind"] == "invalid_output"
    assert out["public_turns"][0]["spoken"] == "I was where I said I was, and that is all."


async def test_unexpected_performer_errors_propagate(case, make_director, fake_performer):
    d = make_director()
    fake_performer.queue = [RuntimeError("bug")]
    with pytest.raises(RuntimeError):
        await d.player_turn({"type": "ask", "suspect_id": "ada", "text": "Well?"})


# ----------------------------------------------------------------------------- confrontation (§8.6)

async def test_confront_alternates_and_interjects(case, make_director, fake_performer):
    d = make_director()
    streamed = []
    interjections = iter(["Stop it, both of you.", None])

    async def on_line(pub):
        streamed.append(pub)

    async def get_interject():
        return next(interjections)

    out = await d.confront({"a": "pell", "b": "ada", "topic": "Who was in the corridor at twenty past eleven?",
                            "rounds": 3}, on_line=on_line, get_interject=get_interject)
    pubs = out["public_turns"]
    assert streamed == pubs
    assert [p["actor"] for p in pubs] == ["pell", "ada", "detective", "pell", "ada", "pell", "ada"]
    assert [p["seq"] for p in pubs] == list(range(1, 8)) and all(p["turn"] == 1 for p in pubs)
    assert pubs[0]["detective_text"] == "Who was in the corridor at twenty past eleven?" and "detective_text" not in pubs[1]
    assert pubs[2]["detective_text"] == "Stop it, both of you." and pubs[2]["target"] is None
    assert pubs[0]["other"] == "ada" and pubs[1]["other"] == "pell" and pubs[0]["target"] == "ada"
    assert all(p["type"] == "confront" for p in pubs) and pubs[-1]["clock"] == "00:30"
    assert_public(pubs)

    ctxs = fake_performer.contexts
    assert len(ctxs) == 6
    assert ctxs[0]["user_message"] == "Detective: Who was in the corridor at twenty past eleven?"
    assert ctxs[0]["confrontation_with"] == {"id": "ada", "name": "Ada Finch"} and ctxs[0]["turn_type"] == "confront"
    assert ctxs[1]["user_message"] == f"Thomas Pell: {pubs[0]['spoken']}"
    assert ctxs[1]["confrontation_with"]["id"] == "pell"
    # after the interjection Pell hears Ada's line and then the detective, in order
    assert ctxs[2]["user_message"] == f"Ada Finch: {pubs[1]['spoken']}\nDetective: Stop it, both of you."
    # Ada heard the interjection before Pell's round-2 line, so her message keeps that order
    assert ctxs[3]["user_message"] == f"Detective: Stop it, both of you.\nThomas Pell: {pubs[3]['spoken']}"
    assert ctxs[4]["user_message"] == f"Ada Finch: {pubs[4]['spoken']}"
    assert_isolated(case, ctxs)

    pell, ada = d.world["suspects"]["pell"], d.world["suspects"]["ada"]
    assert [h["channel"] for h in ada["heard_log"]] == ["confrontation"] * 3
    assert [h["from"] for h in pell["heard_log"]] == ["ada"] * 3 and all(h["turn"] == 1 for h in pell["heard_log"])
    assert ada["heard_log"][0]["text"] == pubs[0]["spoken"]
    # each accused the other every round → +1 each per accusation; nobody decayed
    assert pell["stress"] == 3 and ada["stress"] == 3
    assert pell["last_accuses"] == "ada" and ada["last_accuses"] == "pell"
    # Ada's final line is still in Pell's own transcript even though he never answered it
    assert pell["conversation"][-1] == {"role": "user", "content": f"Ada Finch: {pubs[-1]['spoken']}"}
    assert ada["conversation"][-1]["role"] == "assistant"
    # Ada answered the interjection in round 2: it sits in that round's user message, before Pell's line
    assert ada["conversation"][-4] == {"role": "user",
                                       "content": f"Detective: Stop it, both of you.\nThomas Pell: {pubs[3]['spoken']}"}
    assert len(ada["conversation"]) == 6 and len(pell["conversation"]) == 7
    assert d.world["game"]["turn"] == 1 and d.world["game"]["clock_minutes"] == 30
    rows = out["private_turns"]
    assert [r["actor"] for r in rows] == ["pell", "ada", "detective", "pell", "ada", "pell", "ada"]
    assert rows[0]["stress_before"] == 0 and rows[1]["stress_before"] == 1  # Pell's accusation landed first
    assert rows[2]["output"] is None and rows[2]["input"]["interject"] == "Stop it, both of you."
    wv = out["watson_visible"]
    assert wv["type"] == "confront" and wv["target"] == ["pell", "ada"] and len(wv["lines"]) == 7
    assert "internal_reasoning" not in json.dumps(wv)


async def test_confront_inline_interject_and_reveals(case, make_director, fake_performer):
    d = make_director()
    d.world["suspects"]["ada"]["stress"] = 8
    d.world["suspects"]["ada"]["flatter_count"] = 2  # a3 unlockable
    out = await d.confront({"a": "ada", "b": "pell", "topic": "Ada, tell him about the gloves.", "rounds": 2,
                            "interject": "Go on, Ada."})
    pubs = out["public_turns"]
    assert [p["actor"] for p in pubs] == ["ada", "pell", "detective", "ada", "pell"]
    assert d.world["suspects"]["ada"]["revealed_secret_ids"] == ["a3"]
    # Pell heard the reveal in the room (heard_log), and revealed:a3 now satisfies p1's special unlock
    assert any("gloves" in h["text"] and h["from"] == "ada" for h in d.world["suspects"]["pell"]["heard_log"])
    d.world["suspects"]["pell"]["stress"] = 5
    from app.engine import stress as stress_mod
    assert stress_mod.recompute_unlocks(case, d.world, "pell") == ["p1"]
    assert d.world["game"]["tactics_used"] == {"confront": 1}


async def test_confront_validation(make_director):
    d = make_director()
    for bad in ({"a": "pell", "b": "pell", "topic": "x"}, {"a": "pell", "b": "nobody", "topic": "x"},
                {"a": "pell", "b": "ada", "topic": ""}):
        with pytest.raises(ValueError):
            await d.confront(bad)


# ----------------------------------------------------------------------------- framing + world events

async def test_framing_action_plumbing(case, make_director, fake_performer):
    burn_case = copy.deepcopy(case)
    burn_case["suspects"][2]["framing_actions"][0]["probability"] = 1.0
    d = make_director(case_=burn_case)
    outs = []
    for _ in range(10):
        outs.append(await d.player_turn({"type": "ask", "suspect_id": "crane", "text": "How was his heart?"}))
    assert all(o["world_events"] == [] for o in outs[:9])
    ev = outs[9]["world_events"]
    assert len(ev) == 1 and ev[0]["text"].startswith("Mr. Pell was seen") and ev[0]["evidence"]["id"] == "ashes_in_grate"
    assert_public(ev)
    assert "Mr. Pell was seen coming out of the study, looking pleased with himself." in outs[9]["tickers"]
    rows = [r for r in outs[9]["private_turns"] if r["type"] == "world"]
    assert len(rows) == 1 and rows[0]["actor"] == "director" and rows[0]["target"] == "pell"
    assert d.world["evidence"]["solicitor_letter"]["state"] == "destroyed"
    assert d.world["evidence"]["ashes_in_grate"]["state"] == "known"
    assert d.world["game"]["fired_framing_actions"] == ["burn_letter"]
    ids = [e["id"] for e in world_mod.public_evidence(burn_case, d.world)]
    assert "ashes_in_grate" in ids and "solicitor_letter" not in ids
    out = d.search("study")
    assert out["search"]["examined"] == ["decanter", "ledger", "ashes_in_grate"]


# ----------------------------------------------------------------------------- misc behaviours

async def test_player_signal_normalisation_and_samples(case, make_director, fake_performer):
    d = make_director()
    await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "Hm?", "player_signal": {"voice_stress": 0.9}})
    assert fake_performer.contexts[-1]["player_signal"] == {"voice_stress": 0.9, "composure": "nervous"}
    await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "Hm?", "player_signal": {"gaze": "notebook"}})
    assert fake_performer.contexts[-1]["player_signal"] == {"gaze": "notebook"}
    await d.player_turn({"type": "ask", "suspect_id": "pell", "text": "Hm?"})
    assert fake_performer.contexts[-1]["player_signal"] is None
    assert d.world["game"]["composure_samples"] == [0.2, 0.5]
    assert d.world["game"]["clock_minutes"] == 30


async def test_bluff_composure_changes_stress(case, make_director, fake_performer):
    d = make_director()
    await d.player_turn({"type": "tactic", "tactic": "bluff", "suspect_id": "pell",
                         "player_signal": {"composure": "nervous"}})
    assert d.world["suspects"]["pell"]["stress"] == 0  # 1 + (1-1) - 1
    await d.player_turn({"type": "tactic", "tactic": "bluff", "suspect_id": "pell",
                         "player_signal": {"composure": "confident"}})
    assert d.world["suspects"]["pell"]["stress"] == 2  # 1 + 0 + 1
    assert fake_performer.contexts[-1]["user_message"] == "Detective (bluff): I know more than you think."


async def test_silence_tactic_message(case, make_director, fake_performer):
    d = make_director()
    out = await d.player_turn({"type": "tactic", "tactic": "silence", "suspect_id": "crane"})
    assert fake_performer.contexts[-1]["user_message"] == "The detective says nothing and waits."
    assert "detective_text" not in out["public_turns"][0] and out["public_turns"][0]["tactic"] == "silence"


async def test_wants_to_tell_goes_to_outbox_and_reveal_updates(case, make_director):
    performer = FakePerformer(wants_map={"margaret": {"to": "crane", "message": "They asked about the garden."}})
    d = make_director(performer=performer)
    await d.player_turn({"type": "ask", "suspect_id": "margaret", "text": "Were you in the garden?"})
    m = d.world["suspects"]["margaret"]
    assert m["outbox"] == [{"to": "crane", "text": "They asked about the garden.", "queued_turn": 1}]
    assert m["conversation"][0]["content"] == "Detective: Were you in the garden?"
    assert m["last_honesty"] == "lie" and m["emotion"] == "neutral"
    assert m["last_internal_reasoning"].startswith("I must keep")


async def test_difficulty_scaling_through_director(case, make_director):
    d = make_director(difficulty="rookie")
    await d.player_turn({"type": "tactic", "tactic": "flatter", "suspect_id": "ada"})
    assert d.world["suspects"]["ada"]["stress"] == 6  # (1 + 3) * 1.5
    d2 = make_director(difficulty="inspector", every=3)
    for i in range(2):
        out = await d2.player_turn({"type": "ask", "suspect_id": "ada", "text": "Well?"})
    assert out["offscreen"] is not None  # inspector ticks every 2


async def test_public_suspect_shape(case, make_director):
    d = make_director()
    await d.player_turn({"type": "present", "suspect_id": "pell", "evidence_id": "decanter"})
    cast = d.cast_public()
    pell = next(c for c in cast if c["id"] == "pell")
    assert set(pell) == {"id", "name", "role", "public_description", "portrait_prompt", "portrait_url", "stress_pct",
                         "emotion", "tell", "silenced", "last_seen_location", "voice"}
    assert pell["voice"] == {"webspeech_index": 2, "base_pitch": 0.95}
    assert pell["last_seen_location"] == "study" and pell["silenced"] is False
    assert_public(cast)


def test_director_accepts_performer_objects(case, world, fake_guard, rng):
    class Obj:
        async def perform(self, ctx):
            return {}

    d = Director(case, world, performer=Obj(), guard=fake_guard, rng=rng, difficulty="detective",
                 offscreen_every=3, fallback_lines={})
    assert callable(d.performer)
    with pytest.raises(TypeError):
        Director(case, world, performer=object(), guard=fake_guard, rng=rng, difficulty="detective",
                 offscreen_every=3, fallback_lines={})
