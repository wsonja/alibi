"""Shared fixtures for the engine tests. Runs in scripted mode; nothing here touches an LLM."""
import os

os.environ["LLM_MODE"] = "scripted"
os.environ.setdefault("FAKE_LLM", "1")

import copy
import json
import pathlib
import random
import re
from typing import ClassVar

import pytest

from app.engine import Director
from app.engine import world as world_mod

CASE_PATH = pathlib.Path(__file__).resolve().parents[1] / "app" / "cases" / "vane_hall.json"

FALLBACK_LINES = {
    "margaret": "One has said all one intends to say.",
    "crane": "I think, my friend, that I have said enough.",
    "pell": "I've said all I'm going to say, Inspector.",
    "ada": "I've nothing more to say, sir. If you please.",
}


class LLMUnavailable(Exception):
    """Same class *name* as the agents package raises; the Director dispatches on the name."""


class InvalidOutput(Exception):
    """Same class name as the agents package raises for unparsable model output."""


class FakePerformer:
    """A canned, isolation-safe stand-in for the suspect performer.

    * Records a deep copy of every PerformContext it receives (``contexts``).
    * Detects the topic of the detective's message with keyword rules and answers with a canned dict.
    * Reveals a secret ONLY when its id is in ``ctx["unlocked"]``; otherwise it gives the cover story / a deflection.
    * ``queue`` lets a test force the next raw outputs: a dict is returned as-is, an exception instance is raised,
      a callable is called with the ctx.
    """

    mode = "scripted"

    # (secret id, regex over the lower-cased user message)
    TOPICS: ClassVar[list[tuple[str, str]]] = [
        ("p1", r"cigar|your room|fetch"),
        ("p2", r"manchester|ledger|account|solicitor|partnership|money"),
        ("p3", r"cyanide|poison|decanter|darkroom"),
        ("a1", r"reference|dismiss|sack|character"),
        ("a2", r"corridor|wastebasket|study door"),
        ("a3", r"gloves|saw (mr\.? )?pell|see (mr\.? )?pell|coming out of the study|leave the study"),
        ("m1", r"garden|terrace|headache|bed"),
        ("m2", r"france|crane|lover|affair"),
        ("m3", r"thief|argument|thursday|quarrel"),
        ("c1", r"telephone|call|ring|village"),
        ("c2", r"heart|almond|cyanide|poison"),
        ("c3", r"france|margaret|lover|affair"),
    ]

    def __init__(self, wants_map=None):
        self.contexts = []
        self.calls = 0
        self.queue = []
        self.wants_map = wants_map or {}

    def _topic(self, ctx):
        secrets = {s["id"]: s for s in ctx["suspect"]["secrets"]}
        msg = ctx["user_message"].lower()
        best = None
        for sid, pattern in self.TOPICS:
            if sid in secrets and re.search(pattern, msg) and (best is None or secrets[sid]["tier"] > best["tier"]):
                best = secrets[sid]
        return best

    async def __call__(self, ctx):
        self.calls += 1
        self.contexts.append(copy.deepcopy(ctx))
        suspect = ctx["suspect"]
        ctx["system_blocks"] = [
            f"You are {suspect['name']}, {suspect['role']}. Secrets: "
            + "; ".join(f"[{s['id']}] {s['text']}" for s in suspect["secrets"]),
            f"UNLOCKED: {ctx['unlocked'] or 'none'} LOCKED: {ctx['locked'] or 'none'}",
        ]
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            if callable(item):
                return item(ctx)
            return copy.deepcopy(item)

        base = {
            "internal_reasoning": f"I must keep {', '.join(ctx['locked']) or 'nothing'} to myself.",
            "honesty": "evasive", "emotion": "neutral", "stress_delta": 1, "reveals": [], "accuses": None,
            "wants_to_tell": [], "tell": "",
        }
        other = ctx.get("confrontation_with")
        if ctx["retry_ids"]:
            return {**base, "spoken": "I have nothing more to add on that subject."}
        topic = self._topic(ctx)
        if ctx["turn_type"] == "present":
            base["stress_delta"] = 2
            base["emotion"] = "nervous" if (ctx.get("evidence") or {}).get("points_to_self") else "neutral"
        if topic and topic["id"] in ctx["unlocked"]:
            wants = self.wants_map.get(suspect["id"])
            return {**base, "spoken": f"Very well. {topic['text']}", "honesty": "truthful",
                    "reveals": [topic["id"]], "emotion": "sad", "wants_to_tell": [wants] if wants else []}
        if topic:
            cover = topic.get("cover_story")
            wants = self.wants_map.get(suspect["id"])
            return {**base, "spoken": cover or "I really could not say what you mean.",
                    "honesty": "lie" if cover else "evasive", "wants_to_tell": [wants] if wants else []}
        tt, tactic = ctx["turn_type"], ctx.get("tactic")
        if tt == "present":
            return {**base, "spoken": "That proves nothing at all."}
        if tt == "confront" and other:
            return {**base, "spoken": f"{other['name']}, tell the detective where you were.",
                    "accuses": other["id"], "stress_delta": 0}
        if tactic == "flatter":
            return {**base, "spoken": "You are kind to say so.", "emotion": "smug"}
        if tactic == "threaten":
            return {**base, "spoken": "I should like my solicitor present.", "emotion": "angry"}
        if tactic == "bluff":
            return {**base, "spoken": "I do not believe you."}
        if tactic == "silence":
            return {**base, "spoken": "Is there something else you wanted?"}
        return {**base, "spoken": "I was where I said I was, and that is all.", "honesty": "truthful"}


async def fake_guard_impl(spoken, locked_secrets):
    leaked = [s["id"] for s in locked_secrets if s.get("key_phrases") and re.search(s["key_phrases"], spoken, re.IGNORECASE)]
    return {"leaked": leaked, "reason": "key_phrases matched" if leaked else ""}


@pytest.fixture
def case():
    return json.loads(CASE_PATH.read_text())


@pytest.fixture
def world(case):
    return world_mod.initial_world(case, "detective")


@pytest.fixture
def rng():
    return random.Random(7)


@pytest.fixture
def fake_performer():
    return FakePerformer()


@pytest.fixture
def fake_guard():
    return fake_guard_impl


@pytest.fixture
def make_director(case, rng, fake_performer, fake_guard):
    """Factory: make_director(world=None, case=None, difficulty='detective', every=3, **kw) -> Director."""

    def _make(world=None, case_=None, difficulty="detective", every=3, performer=None, guard=None, **kw):
        c = case_ if case_ is not None else case
        w = world if world is not None else world_mod.initial_world(c, difficulty)
        return Director(
            c, w, performer=performer or fake_performer, guard=guard or fake_guard, rng=kw.pop("rng", rng),
            difficulty=difficulty, offscreen_every=every, fallback_lines=kw.pop("fallback_lines", FALLBACK_LINES),
            **kw,
        )

    return _make
