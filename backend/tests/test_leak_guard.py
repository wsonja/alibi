"""Leak Guard: regex verdicts always, model verdict unioned in gemini mode, graceful fallback."""

import os

os.environ["LLM_MODE"] = "scripted"

import pytest

from app.agents import client as llm
from app.agents import leak_guard

P3 = {"id": "p3", "tier": 3, "text": "He poisoned the decanter with cyanide from the darkroom.", "key_phrases": "cyanide|poison|put (something|it|the powder) in|I killed|I did it"}
P1 = {"id": "p1", "tier": 1, "text": "He went to the study.", "key_phrases": "(went|was) (in|to|into) the study|never went (up )?to my room|didn't go (up )?for (the |my )?cigars"}


async def test_regex_catches_locked_phrase():
    verdict = await leak_guard.check("I put the powder in the brandy myself.", [P1, P3], "scripted")
    assert verdict["leaked"] == ["p3"]
    assert "p3" in verdict["reason"]


async def test_regex_is_case_insensitive_and_reports_every_secret():
    verdict = await leak_guard.check("CYANIDE, yes. I went to the study.", [P1, P3], "scripted")
    assert set(verdict["leaked"]) == {"p1", "p3"}


async def test_clean_line_and_denials_pass():
    verdict = await leak_guard.check("I went up to my room for cigars and came straight back down.", [P1, P3], "scripted")
    assert verdict["leaked"] == []


async def test_nothing_locked_skips_everything(monkeypatch):
    called = False

    async def fake(*args, **kwargs):
        nonlocal called
        called = True
        return {"leaked": ["p3"], "reason": "x"}

    monkeypatch.setattr(llm, "call_tool", fake)
    verdict = await leak_guard.check("I killed him.", [], "gemini")
    assert verdict["leaked"] == [] and not called


async def test_gemini_mode_unions_model_verdict_and_filters_unknown_ids(monkeypatch):
    async def fake(model, system_text, messages, tool, **kwargs):
        assert tool["name"] == "leak_check"
        assert "Locked secrets" in messages[-1]["content"]
        return {"leaked": ["p1", "zzz"], "reason": "the line confirms the study visit"}

    monkeypatch.setattr(llm, "call_tool", fake)
    verdict = await leak_guard.check("Fine. I was near his desk when he stepped out.", [P1, P3], "gemini")
    assert verdict["leaked"] == ["p1"]
    assert "guard model" in verdict["reason"]


async def test_gemini_mode_falls_back_to_regex_when_unavailable(monkeypatch):
    async def fake(*args, **kwargs):
        raise llm.LLMUnavailable("all models failed")

    monkeypatch.setattr(llm, "call_tool", fake)
    verdict = await leak_guard.check("I did it, all right.", [P1, P3], "gemini")
    assert verdict["leaked"] == ["p3"]
    assert "regex only" in verdict["reason"]


def test_bad_regex_does_not_crash():
    assert leak_guard.regex_check("anything", [{"id": "x", "key_phrases": "(unclosed"}]) == []


@pytest.mark.parametrize("mode", ["scripted", "auto", "gemini"])
def test_resolve_mode_honours_env(monkeypatch, mode):
    monkeypatch.setenv("LLM_MODE", mode)
    monkeypatch.delenv("FAKE_LLM", raising=False)
    resolved = llm.resolve_mode()
    if mode == "scripted":
        assert resolved == "scripted"
    elif mode == "gemini":
        assert resolved == "gemini"
    else:
        assert resolved == ("gemini" if llm.credential_available() else "scripted")
    monkeypatch.setenv("FAKE_LLM", "1")
    assert llm.resolve_mode() == "scripted"
    assert llm.resolve_mode({"llm_mode": "gemini", "fake_llm": "1"}) == "scripted"
