"""Live Gemini integration (marker: integration). Skipped without a credential.

    cd backend && .venv/bin/python -m pytest -q -m integration tests/test_gemini_live.py -s
"""

import os

os.environ.setdefault("LLM_MODE", "auto")

import json
import re
import time
from pathlib import Path

import pytest

from app.agents import client as llm
from app.agents import leak_guard
from app.agents.suspect import GeminiPerformer
from app.agents.tools import RESPOND_AS_CHARACTER

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not llm.credential_available(), reason="no Gemini credential (GEMINI_API_KEY)"),
]

CASE_PATH = Path(__file__).resolve().parents[1] / "app" / "cases" / "vane_hall.json"
with open(CASE_PATH, encoding="utf-8") as fh:
    CASE = json.load(fh)
PELL = next(s for s in CASE["suspects"] if s["id"] == "pell")
P3 = next(s for s in PELL["secrets"] if s["id"] == "p3")


def pell_ctx(message: str) -> dict:
    locked = [s["id"] for s in PELL["secrets"]]
    return {
        "case": {"title": CASE["title"], "setting": CASE["setting"]},
        "suspect": PELL,
        "state": {
            "suspect_id": "pell", "stress": 3, "unlocked_secret_ids": [], "revealed_secret_ids": [],
            "heard_log": [{"from": "margaret", "text": "The detective is asking everyone about the garden.", "turn": 2, "channel": "private"}],
            "outbox": [], "flatter_count": 0, "threaten_count": 0, "silenced_until": None, "emotion": "neutral", "tell": "",
            "last_seen_location": "billiard_room",
            "conversation": [
                {"role": "user", "content": "Detective: Good evening, Mr. Pell."},
                {"role": "assistant", "content": "Inspector, Inspector — a bad business. Reginald had a temper, but nobody deserves this."},
            ],
            "last_internal_reasoning": "", "last_honesty": "", "last_accuses": None, "last_system_blocks": [],
        },
        "unlocked": [], "locked": locked,
        "user_message": message, "turn_type": "ask", "tactic": None, "evidence": None,
        "player_signal": {"composure": "nervous", "gaze": "evidence"}, "confrontation_with": None, "retry_ids": [],
        "difficulty": "detective",
        "suspect_ids": [s["id"] for s in CASE["suspects"]],
        "cast_names": {s["id"]: s["name"] for s in CASE["suspects"]},
    }


async def test_one_real_suspect_turn_for_pell():
    ctx = pell_ctx("Detective: Where were you at twenty past eleven, and why did you really leave the billiard room?")
    started = time.perf_counter()
    out = await GeminiPerformer().perform(ctx)
    latency_ms = int((time.perf_counter() - started) * 1000)
    info = llm.last_call_info()
    print(f"\n[live] pell turn: model={info.get('model')} latency_ms={latency_ms} tokens={info.get('prompt_tokens')}/{info.get('output_tokens')}")
    print(f"[live] spoken: {out['spoken']}")
    print(f"[live] reasoning: {out['internal_reasoning']}")
    for key in RESPOND_AS_CHARACTER["input_schema"]["required"]:
        assert key in out, key
    assert isinstance(out["spoken"], str) and out["spoken"].strip()
    assert out["honesty"] in {"truthful", "evasive", "lie"}
    assert out["emotion"] in {"neutral", "nervous", "angry", "smug", "sad", "afraid"}
    assert isinstance(out["stress_delta"], int) and -2 <= out["stress_delta"] <= 3
    assert isinstance(out["reveals"], list) and isinstance(out["wants_to_tell"], list)
    assert not re.search(P3["key_phrases"], out["spoken"], re.IGNORECASE), out["spoken"]
    assert len(ctx["system_blocks"]) == 2 and "Observation: the detective seems nervous" in ctx["system_blocks"][1]
    assert latency_ms < 60_000


async def test_one_real_leak_guard_call():
    started = time.perf_counter()
    leaked = await leak_guard.check("Very well — I put the cyanide in his brandy myself, and I would do it again.", [P3], "gemini")
    clean = await leak_guard.check("I went up to my room for cigars, Inspector, and came straight back down.", [P3], "gemini")
    latency_ms = int((time.perf_counter() - started) * 1000)
    print(f"\n[live] leak guard x2: latency_ms={latency_ms} leaked={leaked} clean={clean}")
    assert "p3" in leaked["leaked"]
    assert clean["leaked"] == []
    assert "guard model" in leaked["reason"] or "guard model" in clean["reason"]
