"""M3 world: search, clock, evidence states, dynamic evidence, framing actions (seeded RNG)."""
import random

from app.engine import public
from app.engine import world as world_mod


def test_clock_starts_at_00_15_and_formats(world):
    assert world["game"]["clock_minutes"] == 15
    assert world_mod.clock_str(15) == "00:15"
    assert world_mod.clock_str(23 * 60 + 5) == "23:05"
    assert world_mod.clock_str(24 * 60 + 5) == "00:05"
    assert world_mod.advance_clock(world, 5) == 20
    assert world_mod.clock_str(world["game"]["clock_minutes"]) == "00:20"


def test_search_examines_and_records(case, world):
    world["game"]["turn"] = 2
    newly = world_mod.search(case, world, "billiard_room")
    assert newly == ["cigar_case"]
    assert world["evidence"]["cigar_case"] == {"state": "examined", "examined_turn": 2}
    assert world["game"]["searched_locations"] == ["billiard_room"]
    assert world["game"]["clock_minutes"] == 25
    assert world_mod.search(case, world, "billiard_room") == []  # second search: nothing new
    assert world["game"]["clock_minutes"] == 35
    assert world["game"]["searched_locations"] == ["billiard_room"]


def test_search_study_examines_known_and_hidden(case, world):
    newly = world_mod.search(case, world, "study")
    assert newly == ["decanter", "solicitor_letter", "ledger"]
    assert "ashes_in_grate" not in newly  # dynamic evidence not in the world yet
    assert world_mod.examined_ids(world) == {"decanter", "solicitor_letter", "ledger"}


def test_search_unknown_location_raises(case, world):
    try:
        world_mod.search(case, world, "attic")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")


def test_public_evidence_hides_hidden_and_details(case, world):
    listed = world_mod.public_evidence(case, world)
    assert [e["id"] for e in listed] == ["decanter"]
    assert listed[0]["state"] == "known" and "examined_detail" not in listed[0]
    world_mod.search(case, world, "study")
    listed = {e["id"]: e for e in world_mod.public_evidence(case, world)}
    assert listed["decanter"]["examined_detail"].startswith("A faint smell")
    assert listed["ledger"]["state"] == "examined"
    assert "cigar_case" not in listed
    assert public.forbidden_keys_present(list(listed.values())) == []


def test_evidence_text_for_present(case, world):
    assert world_mod.evidence_text_for_present(case, world, "decanter") == "Half empty, on the desk beside one used glass."
    world_mod.search(case, world, "study")
    assert world_mod.evidence_text_for_present(case, world, "decanter").startswith("A faint smell of bitter almonds")
    assert world_mod.known_or_examined_ids(world) == {"decanter", "solicitor_letter", "ledger"}
    assert world_mod.is_presentable(world, "decanter") and not world_mod.is_presentable(world, "cigar_case")


def test_burn_letter_fires_deterministically(case, world):
    """Pell burns the letter at turn >= 10 if the study is unsearched; Random(7).random() = 0.32 < 0.7."""
    rng = random.Random(7)
    world["game"]["turn"] = 9
    assert world_mod.evaluate_framing_actions(case, world, rng) == []  # trigger not met, RNG untouched
    world["game"]["turn"] = 10
    fired = world_mod.evaluate_framing_actions(case, world, rng)
    assert len(fired) == 1
    f = fired[0]
    assert f["suspect_id"] == "pell" and f["action_id"] == "burn_letter"
    assert f["ticker"] == "Mr. Pell was seen coming out of the study, looking pleased with himself."
    assert f["evidence"]["id"] == "ashes_in_grate" and f["evidence"]["state"] == "known"
    assert "examined_detail" not in f["evidence"]
    assert world["evidence"]["solicitor_letter"]["state"] == "destroyed"
    assert world["evidence"]["ashes_in_grate"]["state"] == "known"
    assert world["game"]["fired_framing_actions"] == ["burn_letter"]
    # never fires twice
    assert world_mod.evaluate_framing_actions(case, world, rng) == []
    # the destroyed letter was never seen, so it is not listed; the ashes are
    ids = [e["id"] for e in world_mod.public_evidence(case, world)]
    assert "solicitor_letter" not in ids and "ashes_in_grate" in ids
    # searching the study now examines the ashes but not the destroyed letter
    assert world_mod.search(case, world, "study") == ["decanter", "ledger", "ashes_in_grate"]


def test_burn_letter_does_not_fire_when_study_searched(case, world):
    rng = random.Random(7)
    world_mod.search(case, world, "study")
    world["game"]["turn"] = 12
    assert world_mod.evaluate_framing_actions(case, world, rng) == []
    assert world["evidence"]["solicitor_letter"]["state"] == "examined"
    assert rng.random() == random.Random(7).random()  # RNG was not consumed


def test_burn_letter_respects_probability(case, world):
    class Never:
        def random(self):
            return 0.99
    world["game"]["turn"] = 10
    assert world_mod.evaluate_framing_actions(case, world, Never()) == []
    assert world["evidence"]["solicitor_letter"]["state"] == "hidden"


def test_public_locations(case, world):
    world_mod.search(case, world, "garden")
    locs = public.public_locations(case, world)
    assert {"id", "name", "description", "searched"} == set(locs[0])
    assert next(loc for loc in locs if loc["id"] == "garden")["searched"] is True
    assert next(loc for loc in locs if loc["id"] == "study")["searched"] is False
