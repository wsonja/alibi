"""§8.2 math incl. clamps, difficulty scaling, decay; tier unlocks; special_unlocks; monotonic unlocks; shutdown;
Pell's p3 stays locked at stress 99 without the evidence; reveals stripping + event."""
import pytest

from app.engine import stress, validate_output
from app.engine import world as world_mod

PELL_SENS = {"evidence": 4, "threaten": 0, "flatter": 0, "bluff": 1, "silence": 1}
ADA_SENS = {"evidence": 2, "threaten": 2, "flatter": 4, "bluff": 1, "silence": 2}


def delta(model, **kw):
    kw.setdefault("tactic", None)
    kw.setdefault("evidence_points_to_self", None)
    kw.setdefault("sensitivity", PELL_SENS)
    kw.setdefault("composure", None)
    kw.setdefault("difficulty", "detective")
    return stress.compute_delta(model, **kw)


# ----------------------------------------------------------------------------- §8.2

def test_ask_uses_only_model_delta():
    assert delta(2) == 2
    assert delta(0) == 0
    assert delta(-2) == -2


def test_model_delta_is_clamped_to_tool_range():
    assert delta(9) == 3
    assert delta(-9) == -2


def test_tactic_bonus_is_sensitivity_minus_one():
    assert delta(1, tactic="flatter", sensitivity=ADA_SENS) == 1 + (4 - 1)
    assert delta(1, tactic="threaten", sensitivity=PELL_SENS) == 1 + (0 - 1)
    assert delta(0, tactic="silence", sensitivity=ADA_SENS) == 1


def test_evidence_bonus_points_to_self_or_minus_one():
    assert delta(2, evidence_points_to_self=True) == 5  # 2 + 4 = 6 → clamp 5
    assert delta(1, evidence_points_to_self=False) == 0  # 1 - 1
    assert delta(-2, evidence_points_to_self=False) == -2  # -3 → clamp


def test_composure_only_for_bluff_and_threaten():
    assert delta(1, tactic="bluff", composure="nervous") == 1 + 0 - 1
    assert delta(1, tactic="bluff", composure="confident") == 1 + 0 + 1
    assert delta(1, tactic="threaten", sensitivity=ADA_SENS, composure="confident") == 1 + 1 + 1
    assert delta(1, tactic="flatter", sensitivity=ADA_SENS, composure="confident") == 4  # no mod
    assert delta(1, composure="nervous") == 1  # ask: no mod


def test_total_clamped_to_minus2_plus5():
    assert delta(3, tactic="flatter", sensitivity=ADA_SENS) == 5  # 3 + 3 = 6 → 5
    assert delta(-2, tactic="threaten", sensitivity=PELL_SENS, composure="nervous") == -2  # -4 → -2


def test_difficulty_scaling_round_half_up():
    assert delta(1, difficulty="rookie") == 2  # 1.5 → 2
    assert delta(2, difficulty="rookie") == 3
    assert delta(3, difficulty="rookie") == 5  # 4.5 → 5
    assert delta(1, difficulty="inspector") == 1  # 0.75 → 1
    assert delta(2, difficulty="inspector") == 2  # 1.5 → 2
    assert delta(3, difficulty="inspector") == 2  # 2.25 → 2
    assert delta(3, evidence_points_to_self=True, difficulty="inspector") == 4  # 5 * .75 = 3.75 → 4
    assert delta(3, evidence_points_to_self=True, difficulty="rookie") == 8  # 5 * 1.5 = 7.5 → 8
    assert delta(-2, difficulty="rookie") == -2  # negatives are not scaled
    assert delta(-1, difficulty="inspector") == -1
    assert stress.round_half_up(0.5) == 1 and stress.round_half_up(2.5) == 3 and stress.round_half_up(2.4) == 2


def test_apply_delta_floors_at_zero(world):
    assert stress.apply_delta(world, "pell", -2) == (0, 0)
    assert stress.apply_delta(world, "pell", 5) == (0, 5)
    assert stress.apply_delta(world, "pell", -2) == (5, 3)


def test_decay_for_everyone_not_addressed(world):
    for sid in world["suspects"]:
        world["suspects"][sid]["stress"] = 3
    world["suspects"]["ada"]["stress"] = 0
    decayed = stress.apply_decay(world, {"pell"})
    assert world["suspects"]["pell"]["stress"] == 3
    assert world["suspects"]["margaret"]["stress"] == 2
    assert world["suspects"]["crane"]["stress"] == 2
    assert world["suspects"]["ada"]["stress"] == 0  # min 0
    assert decayed == {"margaret": 2, "crane": 2}


def test_stress_pct(case, world):
    pell = case["suspects"][2]
    assert pell["id"] == "pell"
    st = world["suspects"]["pell"]
    assert stress.stress_pct(pell, st) == 0
    st["stress"] = 7
    assert stress.stress_pct(pell, st) == 50  # t3 = 14
    st["stress"] = 30
    assert stress.stress_pct(pell, st) == 100


# ----------------------------------------------------------------------------- §8.3 unlocks

def test_tier_unlocks_follow_thresholds(case, world):
    st = world["suspects"]["margaret"]  # thresholds [4, 8, 12], m2 has a special unlock
    assert stress.recompute_unlocks(case, world, "margaret") == []
    st["stress"] = 4
    assert stress.recompute_unlocks(case, world, "margaret") == ["m1"]
    st["stress"] = 8
    assert stress.recompute_unlocks(case, world, "margaret") == ["m1"]  # m2 needs its special unlock
    st["stress"] = 12
    assert stress.recompute_unlocks(case, world, "margaret") == ["m1", "m2", "m3"]  # stress>=10 satisfies m2
    assert stress.is_unlockable_tier(case["suspects"][0], 12, 3)
    assert not stress.is_unlockable_tier(case["suspects"][0], 11, 3)


def test_special_unlocks_gate_p1(case, world):
    st = world["suspects"]["pell"]
    st["stress"] = 5
    assert stress.recompute_unlocks(case, world, "pell") == []
    world["evidence"]["cigar_case"]["state"] = "examined"
    assert stress.recompute_unlocks(case, world, "pell") == ["p1"]


def test_special_unlock_via_another_suspects_reveal(case, world):
    world["suspects"]["pell"]["stress"] = 5
    world["suspects"]["ada"]["revealed_secret_ids"].append("a3")
    assert stress.recompute_unlocks(case, world, "pell") == ["p1"]


def test_unlocks_are_monotonic(case, world):
    st = world["suspects"]["pell"]
    st["stress"] = 5
    world["evidence"]["cigar_case"]["state"] = "examined"
    assert stress.recompute_unlocks(case, world, "pell") == ["p1"]
    st["stress"] = 0
    assert stress.recompute_unlocks(case, world, "pell") == ["p1"]
    assert st["unlocked_secret_ids"] == ["p1"]


def test_pell_p3_stays_locked_at_99_without_evidence(case, world):
    st = world["suspects"]["pell"]
    st["stress"] = 99
    assert stress.recompute_unlocks(case, world, "pell") == []
    # evidence alone is not enough: p3 also requires p2 revealed
    world["evidence"]["cyanide_jar"]["state"] = "examined"
    assert "p3" not in stress.recompute_unlocks(case, world, "pell")
    world["evidence"]["ledger"]["state"] = "examined"
    assert stress.recompute_unlocks(case, world, "pell") == ["p2"]
    st["revealed_secret_ids"].append("p2")
    assert stress.recompute_unlocks(case, world, "pell") == ["p2", "p3"]
    assert stress.locked_secret_ids(case["suspects"][2], st) == ["p1"]


def test_near_cracks(case, world):
    world["suspects"]["ada"]["stress"] = 1  # t1 = 2 → within 2
    world["suspects"]["pell"]["stress"] = 6  # t1 = 5 but cigar_case missing → special unlock missing
    stress.recompute_unlocks(case, world, "pell")
    near = stress.near_cracks(case, world)
    keys = {(n["suspect_id"], n["secret_id"]) for n in near}
    assert ("ada", "a1") in keys and ("pell", "p1") in keys
    assert ("ada", "a3") not in keys and ("pell", "p3") not in keys
    entry = next(n for n in near if n["secret_id"] == "p1")
    assert entry == {"suspect_id": "pell", "secret_id": "p1", "stress": 6, "threshold": 5}


# ----------------------------------------------------------------------------- §7.3 validation

def ctx_for(case, sid="pell", unlocked=("p1",)):
    return {"suspect": next(s for s in case["suspects"] if s["id"] == sid), "unlocked": list(unlocked),
            "suspect_ids": [s["id"] for s in case["suspects"]]}


def test_reveals_stripped_to_unlocked_with_event(case):
    raw = {"spoken": "I went to the study.", "internal_reasoning": "r", "honesty": "truthful", "emotion": "afraid",
           "stress_delta": 2, "reveals": ["p1", "p3", "a3"], "accuses": None, "wants_to_tell": [], "tell": ""}
    clean, events = validate_output(raw, ctx_for(case))
    assert clean["reveals"] == ["p1"]
    assert [e["kind"] for e in events] == ["reveals_stripped"]
    assert events[0]["detail"]["stripped"] == ["p3", "a3"]


def test_validation_accuses_wants_delta_enums(case):
    raw = {"spoken": " Fine. ", "internal_reasoning": None, "honesty": "sincere", "emotion": "joyful",
           "stress_delta": 7, "reveals": [], "accuses": "butler",
           "wants_to_tell": [{"to": "pell", "message": "self? no"}, {"to": "ada", "message": " careful "},
                             {"to": "nobody", "message": "x"}, {"to": "crane", "message": ""}, "junk"],
           "tell": None}
    clean, events = validate_output(raw, ctx_for(case))
    assert clean["spoken"] == "Fine."
    assert clean["honesty"] == "evasive" and clean["emotion"] == "neutral"
    assert clean["stress_delta"] == 3
    assert clean["accuses"] is None
    assert clean["wants_to_tell"] == [{"to": "ada", "message": "careful"}]
    assert clean["tell"] == "" and clean["internal_reasoning"] == ""
    assert any(e["kind"] == "invalid_output" for e in events)
    clean2, _ = validate_output({"spoken": "x", "stress_delta": -9, "accuses": "ada"}, ctx_for(case))
    assert clean2["stress_delta"] == -2 and clean2["accuses"] == "ada"


def test_validation_non_dict():
    clean, events = validate_output("garbage", {"suspect": {"id": "x"}, "unlocked": [], "suspect_ids": []})
    assert clean["spoken"] == "" and events[0]["kind"] == "invalid_output"


# ----------------------------------------------------------------------------- §8.4 shutdown via the Director

async def test_shutdown_rule_silences_without_a_call(case, make_director, fake_performer):
    d = make_director()
    out = await d.player_turn({"type": "tactic", "tactic": "threaten", "suspect_id": "ada"})
    st = d.world["suspects"]["ada"]
    assert fake_performer.calls == 0
    assert out["public_turns"][0]["spoken"] == case["suspects"][3]["shutdown_rules"]["threaten"]
    assert out["public_turns"][0]["emotion"] == "afraid"
    assert out["private_turns"][0]["output"]["honesty"] == "evasive"
    assert st["stress"] == 2 and st["silenced_until"] == 1 + 2 and st["threaten_count"] == 1
    assert d.cast_public()[3]["silenced"] is True
    # while silenced: ask returns "…" + the line, still no call
    out2 = await d.player_turn({"type": "ask", "text": "Where were you?", "suspect_id": "ada"})
    assert fake_performer.calls == 0
    assert out2["public_turns"][0]["spoken"].startswith("…")
    assert case["suspects"][3]["shutdown_rules"]["threaten"] in out2["public_turns"][0]["spoken"]
    assert st["stress"] == 2
    # present ends the silence early and proceeds normally (performer called)
    out3 = await d.player_turn({"type": "present", "suspect_id": "ada", "evidence_id": "decanter"})
    assert fake_performer.calls == 1
    assert st["silenced_until"] is None
    assert not out3["public_turns"][0]["spoken"].startswith("…")
    assert d.cast_public()[3]["silenced"] is False


async def test_silence_expires_after_two_turns(case, make_director, fake_performer):
    d = make_director()
    await d.player_turn({"type": "tactic", "tactic": "threaten", "suspect_id": "ada"})  # turn 1 → silenced_until 3
    await d.player_turn({"type": "ask", "text": "Well?", "suspect_id": "ada"})  # turn 2 silenced
    assert d.world["suspects"]["ada"]["silenced_until"] == 3 and d.cast_public()[3]["silenced"] is True
    await d.player_turn({"type": "ask", "text": "Well?", "suspect_id": "ada"})  # turn 3 silenced (last turn of it)
    assert fake_performer.calls == 0
    assert d.world["suspects"]["ada"]["silenced_until"] is None  # lapses at the end of its last turn
    assert d.cast_public()[3]["silenced"] is False
    await d.player_turn({"type": "ask", "text": "Well?", "suspect_id": "ada"})  # turn 4 free
    assert fake_performer.calls == 1
    assert d.world["suspects"]["ada"]["silenced_until"] is None


def test_initial_world_shape(case):
    w = world_mod.initial_world(case, "rookie")
    assert w["game"]["difficulty"] == "rookie" and w["game"]["turn"] == 0 and w["game"]["clock_minutes"] == 15
    assert set(w["suspects"]) == {"margaret", "crane", "pell", "ada"}
    st = w["suspects"]["pell"]
    for key in ("suspect_id", "stress", "unlocked_secret_ids", "revealed_secret_ids", "heard_log", "outbox",
                "flatter_count", "threaten_count", "silenced_until", "emotion", "tell", "last_seen_location",
                "conversation", "last_internal_reasoning", "last_honesty", "last_accuses", "last_system_blocks"):
        assert key in st
    assert w["evidence"]["decanter"] == {"state": "known", "examined_turn": None}
    assert w["evidence"]["cigar_case"]["state"] == "hidden"
    assert w["evidence"]["ashes_in_grate"]["state"] == "hidden"


@pytest.mark.parametrize("bad", [
    {"type": "ask", "suspect_id": "butler", "text": "hi"},
    {"type": "ask", "suspect_id": "pell", "text": ""},
    {"type": "tactic", "suspect_id": "pell", "tactic": "bribe"},
    {"type": "present", "suspect_id": "pell", "evidence_id": "cigar_case"},  # hidden: not in possession
    {"type": "confront", "suspect_id": "pell"},
])
async def test_bad_requests_raise(make_director, bad):
    d = make_director()
    with pytest.raises(ValueError):
        await d.player_turn(bad)
