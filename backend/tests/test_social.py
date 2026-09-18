"""M2 social layer: outbox → off-screen tick → heard_log; rumor seeds ignore trust; vague tickers."""
import random

from app.engine import social
from app.engine import world as world_mod


def test_should_tick():
    assert not social.should_tick(0, "detective", 3)
    assert not social.should_tick(2, "detective", 3)
    assert social.should_tick(3, "detective", 3)
    assert social.should_tick(6, "detective", 3)
    assert social.should_tick(2, "inspector", 3)
    assert not social.should_tick(3, "inspector", 3)
    assert not social.should_tick(3, "detective", 0)


def test_queue_wants_to_tell_validates(case, world):
    queued = social.queue_wants_to_tell(case, world, "margaret", [
        {"to": "crane", "message": "Say we were both indoors."},
        {"to": "margaret", "message": "self"},
        {"to": "ghost", "message": "nobody"},
        {"to": "pell", "message": "   "},
        "junk",
    ], turn=2)
    assert queued == [{"to": "crane", "text": "Say we were both indoors.", "queued_turn": 2}]
    assert world["suspects"]["margaret"]["outbox"] == queued


def test_stories_align_only_after_a_tick(case, world, rng):
    """Margaret tells Crane what to say; Crane knows nothing until the off-screen tick delivers it."""
    world["game"]["turn"] = 3
    social.queue_wants_to_tell(case, world, "margaret", [{"to": "crane", "message": "I said I was in bed at eleven. Say the same."}], 3)
    assert world["suspects"]["crane"]["heard_log"] == []
    deliveries = social.run_offscreen_tick(case, world, rng)
    heard = world["suspects"]["crane"]["heard_log"]
    assert any(h["from"] == "margaret" and "bed at eleven" in h["text"] and h["channel"] == "private" and h["turn"] == 3
               for h in heard)
    assert any(d["from"] == "margaret" and d["to"] == "crane" for d in deliveries)
    assert world["suspects"]["margaret"]["outbox"] == []
    assert world["game"]["offscreen_ticks"] == 1


def test_rumor_seed_reaches_ada_despite_zero_trust(case, world, rng):
    assert case["suspects"][2]["relationships"]["ada"]["trust"] == 0.0
    world["game"]["turn"] = 3
    deliveries = social.run_offscreen_tick(case, world, rng)
    seed_text = case["rumor_seeds"][0]["text"]
    to_ada = [d for d in deliveries if d["from"] == "pell" and d["to"] == "ada"]
    assert to_ada and to_ada[0]["text"] == seed_text and to_ada[0]["seed"] is True
    assert any(h["text"] == seed_text and h["from"] == "pell" for h in world["suspects"]["ada"]["heard_log"])
    assert any(h["text"] == seed_text for h in world["suspects"]["crane"]["heard_log"])
    assert not any(h["text"] == seed_text for h in world["suspects"]["margaret"]["heard_log"])
    # seeds are queued once only
    world["game"]["turn"] = 6
    second = social.run_offscreen_tick(case, world, rng)
    assert second == []


def test_untrusted_message_is_dropped(case, world, rng):
    world["game"]["turn"] = 3
    social.queue_wants_to_tell(case, world, "pell", [{"to": "ada", "message": "Keep your mouth shut about the gloves."}], 3)
    social.queue_wants_to_tell(case, world, "ada", [{"to": "crane", "message": "I am frightened of Mr. Pell."}], 3)
    dropped = []
    deliveries = social.run_offscreen_tick(case, world, rng, dropped=dropped)
    assert not any("gloves" in h["text"] for h in world["suspects"]["ada"]["heard_log"])
    assert any(d["text"].startswith("Keep your mouth") for d in dropped)
    assert any(d["from"] == "ada" and d["to"] == "crane" for d in deliveries)  # trusts, 0.8
    assert social.can_deliver(case["suspects"][0], {"to": "ada"})  # employer 0.5 → threshold
    assert not social.can_deliver(case["suspects"][0], {"to": "pell"})  # dislikes 0.2
    assert social.can_deliver(case["suspects"][0], {"to": "pell", "seed": True})


def test_add_heard(world):
    social.add_heard(world, "ada", "crane", "Be brave.", 4, "confrontation")
    assert world["suspects"]["ada"]["heard_log"] == [{"from": "crane", "text": "Be brave.", "turn": 4, "channel": "confrontation"}]


async def test_ticker_never_contains_message_text(case, make_director, fake_performer):
    wants = {"margaret": {"to": "crane", "message": "They asked about the garden. Remember: bed at eleven."}}
    performer = type(fake_performer)(wants_map=wants)
    d = make_director(performer=performer)
    outcomes = []
    for _ in range(3):
        outcomes.append(await d.player_turn({"type": "ask", "text": "Were you in the garden?", "suspect_id": "margaret"}))
    assert outcomes[0]["offscreen"] is None and outcomes[1]["offscreen"] is None
    tick = outcomes[2]["offscreen"]
    assert tick is not None
    delivered_texts = [x["text"] for x in tick["deliveries"]]
    assert any("bed at eleven" in t for t in delivered_texts)
    assert case["rumor_seeds"][0]["text"] in delivered_texts
    assert outcomes[2]["tickers"], "a tick pushes a ticker line"
    for line in outcomes[2]["tickers"]:
        assert line in case["ticker_lines"]
        for text in delivered_texts:
            assert text not in line and line not in text
    offscreen_rows = [r for r in outcomes[2]["private_turns"] if r["type"] == "offscreen"]
    assert len(offscreen_rows) == 1 and offscreen_rows[0]["actor"] == "director"
    assert offscreen_rows[0]["output"]["deliveries"] == tick["deliveries"]
    assert any(h["from"] == "margaret" and h["channel"] == "private" for h in d.world["suspects"]["crane"]["heard_log"])
    # the message is provenance-tagged with the turn of delivery
    assert all(h["turn"] == 3 for h in d.world["suspects"]["crane"]["heard_log"])


def test_inspector_ticks_every_two(case, rng):
    w = world_mod.initial_world(case, "inspector")
    assert social.should_tick(2, w["game"]["difficulty"], 3)
    assert isinstance(social.pick_ticker(case, random.Random(1)), str)
