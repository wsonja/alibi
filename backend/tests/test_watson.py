"""Watson (rule-based notebook): claims with normalised times, contradictions, suggestions."""

import os

os.environ["LLM_MODE"] = "scripted"

import json
from pathlib import Path

from app.agents import client as llm
from app.agents import watson

CASE_PATH = Path(__file__).resolve().parents[1] / "app" / "cases" / "vane_hall.json"
with open(CASE_PATH, encoding="utf-8") as fh:
    CASE = json.load(fh)
CAST = [{"id": s["id"], "name": s["name"], "role": s["role"]} for s in CASE["suspects"]]
LOCATIONS = [{"id": loc["id"], "name": loc["name"], "searched": loc["id"] == "study"} for loc in CASE["locations"]]


def visible(turns, evidence=None, turn=None):
    return {
        "turns": turns,
        "evidence": evidence or [{"id": "decanter", "name": "The brandy decanter"}],
        "timeline_public": CASE["timeline_public"],
        "cast": CAST,
        "locations": LOCATIONS,
        "turn": turn if turn is not None else len(turns),
    }


def test_time_phrases_normalise_to_hhmm():
    def t(s):
        return [v for _, v in watson.parse_times(s, pm=True)]

    assert t("I went up at eleven.") == ["23:00"]
    assert t("It was half past ten when I left.") == ["22:30"]
    assert t("At twenty past eleven I was in my room.") == ["23:20"]
    assert t("Ten to eleven, perhaps.") == ["22:50"]
    assert t("Around 11:20, I think.") == ["23:20"]
    assert t("A quarter to twelve.") == ["23:45"]
    assert t("twenty-one minutes past eleven") == ["23:21"]
    assert t("from eleven until half past eleven") == ["23:00", "23:30"]
    assert t("twenty to midnight") == ["23:40"]


async def test_claims_and_cross_suspect_contradiction():
    turns = [
        {"turn": 1, "type": "ask", "target": "pell", "detective_text": "Where were you at 11:20?", "spoken": "I went up to my room for cigars at twenty past eleven, Inspector, and came straight back down."},
        {"turn": 2, "type": "ask", "target": "ada", "detective_text": "What did you see?", "spoken": "I saw Mr. Pell leave the study at twenty past eleven, sir. He was pulling off gloves."},
    ]
    entry = await watson.update(visible(turns), "scripted")
    assert entry["turn"] == 2
    by = {p["id"]: p for p in entry["per_suspect"]}
    assert set(by) == {"margaret", "crane", "pell", "ada"}
    pell_claims = by["pell"]["claims"]
    assert pell_claims and pell_claims[0]["where"] == "my room"
    assert pell_claims[0]["from"] == "23:20" and pell_claims[0]["to"] == "23:20"
    assert by["pell"]["notes"] and "Turn 1" in by["pell"]["notes"][0]
    assert entry["contradictions"], "Ada's sighting should contradict Pell's alibi"
    con = entry["contradictions"][0]
    assert con["a"]["suspect"] == "pell" and con["b"]["suspect_or_evidence"] == "ada"
    assert "study" in con["note"]
    assert len(entry["suggested_next"]) >= 3
    assert any("Confront" in s and "Pell" in s for s in entry["suggested_next"])


async def test_same_suspect_contradiction_and_whole_evening_claims():
    turns = [
        {"turn": 1, "type": "ask", "target": "margaret", "detective_text": "Where were you?", "spoken": "I went up to bed with a headache at eleven and heard nothing."},
        {"turn": 2, "type": "ask", "target": "margaret", "detective_text": "Really?", "spoken": "Very well. I was in the garden at eleven; the necklace broke on the bench."},
        {"turn": 3, "type": "ask", "target": "ada", "detective_text": "And you?", "spoken": "I was in the kitchen all evening, sir."},
    ]
    entry = await watson.update(visible(turns), "scripted")
    by = {p["id"]: p for p in entry["per_suspect"]}
    wheres = [c["where"] for c in by["margaret"]["claims"]]
    assert "upstairs" in wheres and "garden" in wheres
    self_con = [c for c in entry["contradictions"] if c["a"]["suspect"] == "margaret" and c["b"]["suspect_or_evidence"] == "margaret"]
    assert self_con
    ada_claim = by["ada"]["claims"][0]
    assert ada_claim["where"] == "kitchen" and ada_claim["from"] == "22:30" and ada_claim["to"] == "23:45"


async def test_negated_locations_are_not_claims():
    turns = [{"turn": 1, "type": "ask", "target": "margaret", "detective_text": "?", "spoken": "I did not go near the study all evening."}]
    entry = await watson.update(visible(turns), "scripted")
    by = {p["id"]: p for p in entry["per_suspect"]}
    assert all(c["where"] != "study" for c in by["margaret"]["claims"])


async def test_suggestions_are_concrete_and_use_visible_state():
    turns = [{"turn": 1, "type": "ask", "target": "pell", "detective_text": "?", "spoken": "Inspector, Inspector. Reginald had a temper."}]
    evidence = [
        {"id": "cigar_case", "name": "Mr. Pell's cigar case", "examined_detail": "Silver, monogrammed T.P. Mr. Pell did not need to fetch his cigars from anywhere."},
        {"id": "ledger", "name": "The partnership ledger", "location": "study"},
    ]
    entry = await watson.update(visible(turns, evidence=evidence), "scripted")
    s = entry["suggested_next"]
    assert len(s) == 3
    assert any("Present Mr. Pell's cigar case to Thomas Pell" in x for x in s)
    assert any(x.startswith("Ask ") for x in s)


async def test_empty_game_still_produces_a_notebook():
    entry = await watson.update(visible([], turn=0), "scripted")
    assert entry["per_suspect"] and entry["contradictions"] == [] and len(entry["suggested_next"]) == 3


async def test_gemini_mode_falls_back_to_rules_when_unavailable(monkeypatch):
    async def fake(*args, **kwargs):
        raise llm.LLMUnavailable("down")

    monkeypatch.setattr(llm, "call_tool", fake)
    turns = [{"turn": 1, "type": "ask", "target": "ada", "detective_text": "?", "spoken": "I was in the kitchen at eleven, sir."}]
    entry = await watson.update(visible(turns), "gemini")
    assert entry["per_suspect"] and entry["suggested_next"]


async def test_gemini_mode_normalises_model_output(monkeypatch):
    async def fake(model, system_text, messages, tool, **kwargs):
        assert tool["name"] == "notebook_update"
        assert "internal_reasoning" not in messages[-1]["content"]
        return {
            "per_suspect": [{"id": "ada", "claims": [{"quote": "kitchen", "where": "kitchen", "from": "23:00", "to": ""}], "notes": ["nervous"]}, {"id": "nobody", "claims": [], "notes": []}],
            "contradictions": [],
            "suggested_next": ["Search the Darkroom."],
        }

    monkeypatch.setattr(llm, "call_tool", fake)
    turns = [{"turn": 1, "type": "ask", "target": "ada", "detective_text": "?", "spoken": "I was in the kitchen at eleven, sir."}]
    entry = await watson.update(visible(turns), "gemini")
    ids = [p["id"] for p in entry["per_suspect"]]
    assert "nobody" not in ids and set(ids) == {"margaret", "crane", "pell", "ada"}
    assert entry["suggested_next"][0] == "Search the Darkroom." and len(entry["suggested_next"]) >= 3
