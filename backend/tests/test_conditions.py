"""Condition DSL (PLAN §6, §15): every token, and/or/not, precedence, unknown token raises, context_for."""
import pytest

from app.engine import ConditionError, conditions, context_for, evaluate, rule_holds
from app.engine import world as world_mod


def ctx(**over):
    base = {"examined": set(), "known": set(), "revealed": set(), "stress": 0, "flatter_count": 0,
            "threaten_count": 0, "turn": 0, "searched": set(), "clock_minutes": 15}
    base.update(over)
    return base


def test_evidence_token_requires_examined():
    assert evaluate("evidence:decanter", ctx(examined={"decanter"}))
    assert not evaluate("evidence:decanter", ctx(known={"decanter"}))
    assert not evaluate("evidence:decanter", ctx())


def test_known_token_true_for_known_or_examined():
    assert evaluate("known:decanter", ctx(known={"decanter"}))
    assert evaluate("known:decanter", ctx(examined={"decanter"}))
    assert not evaluate("known:decanter", ctx())


def test_revealed_token():
    assert evaluate("revealed:a3", ctx(revealed={"a3"}))
    assert not evaluate("revealed:a3", ctx())


def test_numeric_tokens():
    assert evaluate("stress>=5", ctx(stress=5))
    assert not evaluate("stress>=5", ctx(stress=4))
    assert evaluate("flatter_count>=2", ctx(flatter_count=2))
    assert not evaluate("flatter_count>=2", ctx(flatter_count=1))
    assert evaluate("threaten_count>=1", ctx(threaten_count=3))
    assert evaluate("turn>=10", ctx(turn=10))
    assert not evaluate("turn>=10", ctx(turn=9))


def test_searched_token():
    assert evaluate("searched:study", ctx(searched={"study"}))
    assert not evaluate("searched:study", ctx())


def test_clock_token():
    assert evaluate("clock>=00:15", ctx(clock_minutes=15))
    assert evaluate("clock>=01:00", ctx(clock_minutes=61))
    assert not evaluate("clock>=01:00", ctx(clock_minutes=59))
    assert conditions.parse_clock("23:20") == 23 * 60 + 20


def test_not_prefix():
    assert evaluate("not searched:study", ctx())
    assert not evaluate("not searched:study", ctx(searched={"study"}))
    assert evaluate("not evidence:decanter and turn>=1", ctx(turn=1))


def test_and_or():
    c = ctx(examined={"cigar_case"}, turn=3)
    assert evaluate("evidence:cigar_case and turn>=3", c)
    assert not evaluate("evidence:cigar_case and turn>=4", c)
    assert evaluate("evidence:cigar_case or turn>=4", c)
    assert evaluate("evidence:nope or turn>=3", c)
    assert not evaluate("evidence:nope or turn>=4", c)


def test_and_binds_tighter_than_or():
    # a or (b and c): a true → true even though b and c are false
    c = ctx(examined={"decanter"})
    assert evaluate("evidence:decanter or evidence:ledger and turn>=99", c)
    # (a and b) or c with a true, b false, c false → false; if it were a and (b or c) it would also be false, so:
    c2 = ctx(examined={"ledger"}, turn=99)
    # evidence:decanter false; "evidence:decanter and evidence:ledger or turn>=99" = (F and T) or T = T
    assert evaluate("evidence:decanter and evidence:ledger or turn>=99", c2)
    # under wrong precedence a and (b or c) it would be F and (T or T) = F
    c3 = ctx(examined=set(), turn=99)
    assert not evaluate("evidence:decanter and turn>=99 or evidence:ledger", c3)


def test_pell_burn_trigger_from_case():
    assert evaluate("turn>=10 and not searched:study", ctx(turn=10))
    assert not evaluate("turn>=10 and not searched:study", ctx(turn=10, searched={"study"}))
    assert not evaluate("turn>=10 and not searched:study", ctx(turn=9))


@pytest.mark.parametrize("expr", ["bogus:thing", "stress>5", "stress>=x", "evidence", "", "   ", "not ",
                                  "evidence:decanter and", "(evidence:decanter)", "clock>=25:00", "known decanter"])
def test_unknown_token_raises(expr):
    with pytest.raises(ConditionError):
        evaluate(expr, ctx())


def test_every_case_condition_parses(case):
    for s in case["suspects"]:
        for rule in s["special_unlocks"].values():
            for c in rule.get("requires_any", []) + rule.get("requires_all", []):
                conditions.parse(c)
        for fa in s["framing_actions"]:
            conditions.parse(fa["trigger"])
    for path in case["solution"]["proof_paths"]:
        for tok in path:
            conditions.parse(tok)


def test_context_for_reflects_world(case):
    world = world_mod.initial_world(case, "detective")
    world["game"]["turn"] = 4
    world["game"]["searched_locations"].append("garden")
    world["evidence"]["cigar_case"]["state"] = "examined"
    world["suspects"]["pell"]["stress"] = 6
    world["suspects"]["pell"]["flatter_count"] = 1
    world["suspects"]["ada"]["revealed_secret_ids"].append("a3")  # another suspect's reveal is visible
    c = context_for(case, world, "pell")
    assert c["turn"] == 4 and c["stress"] == 6 and c["flatter_count"] == 1 and c["threaten_count"] == 0
    assert "garden" in c["searched"]
    assert "cigar_case" in c["examined"] and "cigar_case" in c["known"]
    assert "decanter" in c["known"] and "decanter" not in c["examined"]  # initially known, not examined
    assert "a3" in c["revealed"]
    assert c["clock_minutes"] == 15
    assert evaluate("evidence:cigar_case or revealed:a3", c)


def test_rule_holds_any_all_revealed():
    c = ctx(examined={"cyanide_jar"}, revealed={"p2"}, stress=20)
    assert rule_holds(None, c)
    assert rule_holds({}, c)
    assert rule_holds({"requires_any": ["evidence:cigar_ash", "evidence:cyanide_jar"], "requires_revealed": ["p2"]}, c)
    assert not rule_holds({"requires_any": ["evidence:cigar_ash"]}, c)
    assert not rule_holds({"requires_revealed": ["p1"]}, c)
    assert rule_holds({"requires_all": ["stress>=10", "revealed:p2"]}, c)
    assert not rule_holds({"requires_all": ["stress>=10", "revealed:p1"]}, c)
