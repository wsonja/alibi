"""Static case checker (port of scripts/validate_case.py) and the judge helpers."""

import os

os.environ["LLM_MODE"] = "scripted"

import copy
import json
from pathlib import Path

from app.agents import client as llm
from app.agents import judge
from app.agents.checker import static_check
from app.agents.tools import ALL_TOOLS, RESPOND_AS_CHARACTER, WRITE_CASE

CASE_PATH = Path(__file__).resolve().parents[1] / "app" / "cases" / "vane_hall.json"
with open(CASE_PATH, encoding="utf-8") as fh:
    CASE = json.load(fh)


def suspect(case, sid):
    return next(s for s in case["suspects"] if s["id"] == sid)


def test_vane_hall_passes():
    assert static_check(CASE) == []


def test_two_guilty_fails():
    case = copy.deepcopy(CASE)
    suspect(case, "ada")["guilty"] = True
    errs = static_check(case)
    assert "expected exactly one guilty, got 2" in errs
    assert "ada: confession secret" in errs


def test_bad_dsl_token_fails():
    case = copy.deepcopy(CASE)
    suspect(case, "margaret")["special_unlocks"]["m2"]["requires_any"][0] = "evidenc:necklace_clasp"
    errs = static_check(case)
    assert any(e.startswith("margaret/m2: bad token") for e in errs)


def test_confession_without_physical_evidence_fails():
    case = copy.deepcopy(CASE)
    suspect(case, "pell")["special_unlocks"]["p3"] = {"requires_revealed": ["p2"]}
    errs = static_check(case)
    assert "pell: confession must require physical evidence" in errs


def test_unsatisfiable_proof_path_and_dangling_ids_fail():
    case = copy.deepcopy(CASE)
    case["solution"]["proof_paths"][0] = ["revealed:p3"]
    case["locations"][0]["evidence_ids"].append("ghost")
    case["suspects"][0]["relationships"].pop("pell")
    errs = static_check(case)
    assert "proof_path[0]: revealed:p3 not unlockable at that point" in errs
    assert "location study: unknown evidence ghost" in errs
    assert "margaret: relationships incomplete" in errs


def test_missing_keys_do_not_crash():
    assert static_check({}) == ["missing top-level key suspects", "missing top-level key evidence", "missing top-level key locations", "missing top-level key solution"]
    case = copy.deepcopy(CASE)
    del suspect(case, "crane")["tells"]
    suspect(case, "crane")["secrets"][0]["key_phrases"] = "(unclosed"
    errs = static_check(case)
    assert "crane: missing tells" in errs and "crane: tells" in errs
    assert any(e.startswith("crane/c1: bad key_phrases regex") for e in errs)


def test_tool_schemas_are_well_formed():
    assert RESPOND_AS_CHARACTER["input_schema"]["properties"]["accuses"]["type"] == ["string", "null"]
    assert set(RESPOND_AS_CHARACTER["input_schema"]["required"]) == {"spoken", "internal_reasoning", "honesty", "emotion", "stress_delta", "reveals", "accuses", "wants_to_tell", "tell"}
    case_schema = WRITE_CASE["input_schema"]
    for key in ("id", "title", "setting", "briefing", "victim", "timeline_public", "timeline_truth", "locations", "evidence", "dynamic_evidence", "suspects", "solution", "red_herrings", "rumor_seeds", "ticker_lines"):
        assert key in case_schema["required"] and key in case_schema["properties"]
    suspect_schema = case_schema["properties"]["suspects"]["items"]
    assert set(suspect_schema["required"]) >= {"id", "name", "secrets", "special_unlocks", "relationships", "guilty"}
    for name, tool in ALL_TOOLS.items():
        assert tool["name"] == name and tool["input_schema"]["type"] == "object"
        json.dumps(tool["input_schema"])


def test_grade_motive_scripted_buckets():
    truth = CASE["solution"]["motive"]
    full = judge.grade_motive_scripted("Reginald had discovered Pell was embezzling from the Manchester accounts and meant to dissolve the partnership and go to the police.", truth)
    assert full["points"] == 20
    partial = judge.grade_motive_scripted("He was embezzling money and Reginald was going to the police.", truth)
    assert partial["points"] == 10
    wrong = judge.grade_motive_scripted("He was jealous of the affair.", truth)
    assert wrong["points"] == 0
    assert all(g["note"] for g in (full, partial, wrong))


async def test_grade_motive_gemini_falls_back(monkeypatch):
    async def fake(*args, **kwargs):
        raise llm.LLMUnavailable("down")

    monkeypatch.setattr(llm, "call_tool", fake)
    out = await judge.grade_motive("embezzling from the Manchester accounts, police", CASE["solution"]["motive"], "gemini")
    assert out["points"] in (10, 20)


async def test_fallback_lines_are_in_character():
    lines = await judge.fallback_lines(CASE, "scripted")
    assert set(lines) == {"margaret", "crane", "pell", "ada"}
    assert "One has said" in lines["margaret"]
    assert "solicitor" in lines["pell"]
    assert "sir" in lines["ada"]
    assert "my friend" in lines["crane"]


async def test_summarize_scripted_is_extractive():
    messages = [{"role": "user", "content": "Detective: Where were you?"}, {"role": "assistant", "content": "In my room, Inspector. Fetching cigars."}]
    summary = await judge.summarize(messages, "scripted")
    assert "Where were you?" in summary and "In my room, Inspector." in summary
