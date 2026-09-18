"""The Director — deterministic turn orchestration (PLAN §7.2–§7.4 message/validation/guard, §8.1–§8.10).

The Director never imports an LLM SDK. It receives injected async callables:

``performer(ctx) -> raw dict``  — performs ONE suspect for ONE turn from a PerformContext (INTERFACES §3); it may set
``ctx["system_blocks"]`` to the exact system text it used (kept for the Judge Panel).
``guard(spoken, locked_secrets) -> {"leaked": [...], "reason": str}`` — the Leak Guard.

Every public method returns a TurnOutcome::

    {"public_turns": [PublicTurn], "private_turns": [turn rows], "guard_events": [...], "world_events": [...],
     "tickers": [str], "offscreen": {"deliveries": [...], "dropped": [...], "ticker": str|None} | None,
     "watson_visible": {...} | None, "clock": "HH:MM"}

plus ``"search"`` (search) and ``"accusation"`` (accuse).
"""
from __future__ import annotations

import copy
import inspect
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

from . import scoring, social
from . import stress as stress_mod
from . import world as world_mod
from .public import public_turn

__all__ = [
    "DEFAULT_FALLBACK_LINE",
    "DEFAULT_TACTIC_TEXT",
    "EMOTION_VALUES",
    "GUARD_KINDS",
    "HONESTY_VALUES",
    "PLAYER_TURN_TYPES",
    "SILENCE_TEXT",
    "TACTICS",
    "Director",
    "DirectorError",
    "GameClosed",
    "empty_output",
    "format_user_message",
    "normalize_player_signal",
    "validate_output",
]

PLAYER_TURN_TYPES = ("ask", "tactic", "present")
TACTICS = ("bluff", "flatter", "threaten", "silence")
DEFAULT_TACTIC_TEXT = {
    "bluff": "I know more than you think.",
    "flatter": "You strike me as the only sensible person in this house.",
    "threaten": "I can make this very unpleasant for you.",
}
SILENCE_TEXT = "The detective says nothing and waits."
DEFAULT_FALLBACK_LINE = "I have said all I am going to say."
HONESTY_VALUES = ("truthful", "evasive", "lie")
EMOTION_VALUES = ("neutral", "nervous", "angry", "smug", "sad", "afraid")
COMPOSURE_VALUES = ("nervous", "neutral", "confident")
GAZE_VALUES = ("suspect", "evidence", "notebook", "away")
COMPOSURE_SAMPLE = {"nervous": 0.2, "neutral": 0.5, "confident": 0.9}
GUARD_KINDS = ("reveals_stripped", "leak_regenerated", "leak_fallback", "invalid_output", "llm_fallback_scripted")
MAX_LEAK_RETRIES = 2
DEFAULT_ROUNDS = 3
MAX_ROUNDS = 6
SILENCE_TURNS = 2
SHUTDOWN_STRESS = 2
CONFRONT_ACCUSED_STRESS = 1


class DirectorError(ValueError):
    """A malformed or impossible request (unknown suspect, evidence not known, bad tactic ...)."""


class GameClosed(DirectorError):
    """The game is closed; no further actions are possible."""


# ----------------------------------------------------------------------------- pure helpers

def format_user_message(
    turn_type: str,
    *,
    text: str | None = None,
    tactic: str | None = None,
    evidence_name: str | None = None,
    evidence_text: str | None = None,
    speaker_name: str | None = None,
    spoken: str | None = None,
) -> str:
    """PLAN §7.2 user-message formats."""
    text = (text or "").strip()
    if turn_type == "ask":
        return f"Detective: {text}"
    if turn_type == "tactic":
        if tactic == "silence":
            return SILENCE_TEXT
        body = text or DEFAULT_TACTIC_TEXT.get(tactic or "", "")
        return f"Detective ({tactic}): {body}"
    if turn_type == "present":
        msg = f"The detective shows you: {evidence_name}. {evidence_text or ''}".rstrip()
        if text:
            msg += f"\nDetective: {text}"
        return msg
    if turn_type == "confront":
        return f"{speaker_name}: {spoken or ''}"
    if turn_type == "interject":
        return f"Detective: {text}"
    raise DirectorError(f"unknown turn type {turn_type!r}")


def normalize_player_signal(signal: Any) -> dict | None:
    """PLAN §8.5: keep only the known fields; composure absent + voice_stress > 0.7 → nervous."""
    if not isinstance(signal, dict):
        return None
    out: dict[str, Any] = {}
    composure = signal.get("composure")
    if composure in COMPOSURE_VALUES:
        out["composure"] = composure
    gaze = signal.get("gaze")
    if gaze in GAZE_VALUES:
        out["gaze"] = gaze
    voice = signal.get("voice_stress")
    if isinstance(voice, (int, float)) and not isinstance(voice, bool):
        out["voice_stress"] = float(max(0.0, min(1.0, voice)))
        if "composure" not in out and out["voice_stress"] > 0.7:
            out["composure"] = "nervous"
    return out or None


def empty_output(spoken: str = "", **overrides: Any) -> dict:
    out = {
        "spoken": spoken, "internal_reasoning": "", "honesty": "evasive", "emotion": "neutral", "stress_delta": 0,
        "reveals": [], "accuses": None, "wants_to_tell": [], "tell": "",
    }
    out.update(overrides)
    return out


def validate_output(raw: Any, ctx: dict) -> tuple[dict, list[dict]]:
    """PLAN §7.3 validation. Returns ``(clean, events)`` where events are ``{"kind", "detail"}`` dicts.

    reveals ⊆ unlocked else stripped (+ ``reveals_stripped``); accuses ∈ suspect ids else None;
    wants_to_tell[].to ∈ suspect ids and ≠ self else dropped; stress_delta clamped to [-2, 3]; enum fields coerced
    (+ ``invalid_output``). An empty ``spoken`` is returned as "" for the caller to retry/fallback.
    """
    events: list[dict] = []
    self_id = (ctx.get("suspect") or {}).get("id")
    suspect_ids = set(ctx.get("suspect_ids") or [])
    unlocked = list(ctx.get("unlocked") or [])
    if not isinstance(raw, dict):
        events.append({"kind": "invalid_output", "detail": {"reason": "not an object", "type": type(raw).__name__}})
        return empty_output(), events
    invalid_fields: dict[str, Any] = {}

    spoken = raw.get("spoken")
    if not isinstance(spoken, str):
        if spoken is not None:
            invalid_fields["spoken"] = repr(spoken)[:80]
        spoken = ""
    spoken = spoken.strip()

    reasoning = raw.get("internal_reasoning")
    reasoning = reasoning.strip() if isinstance(reasoning, str) else ""

    honesty = raw.get("honesty")
    if honesty not in HONESTY_VALUES:
        if honesty is not None:
            invalid_fields["honesty"] = repr(honesty)[:80]
        honesty = "evasive"

    emotion = raw.get("emotion")
    if emotion not in EMOTION_VALUES:
        if emotion is not None:
            invalid_fields["emotion"] = repr(emotion)[:80]
        emotion = "neutral"

    delta_raw = raw.get("stress_delta", 0)
    try:
        delta = round(float(delta_raw)) if not isinstance(delta_raw, bool) else 0
    except (TypeError, ValueError):
        invalid_fields["stress_delta"] = repr(delta_raw)[:80]
        delta = 0
    if delta < stress_mod.MODEL_DELTA_MIN or delta > stress_mod.MODEL_DELTA_MAX:
        delta = int(stress_mod.clamp(delta, stress_mod.MODEL_DELTA_MIN, stress_mod.MODEL_DELTA_MAX))

    reveals_raw = raw.get("reveals")
    if not isinstance(reveals_raw, list):
        if reveals_raw is not None:
            invalid_fields["reveals"] = repr(reveals_raw)[:80]
        reveals_raw = []
    reveals: list[str] = []
    stripped: list[str] = []
    for r in reveals_raw:
        if not isinstance(r, str):
            stripped.append(repr(r)[:40])
            continue
        if r in unlocked:
            if r not in reveals:
                reveals.append(r)
        else:
            stripped.append(r)
    if stripped:
        events.append({"kind": "reveals_stripped", "detail": {"stripped": stripped, "unlocked": unlocked}})

    accuses = raw.get("accuses")
    if not (isinstance(accuses, str) and accuses in suspect_ids):
        accuses = None

    wants_raw = raw.get("wants_to_tell")
    if not isinstance(wants_raw, list):
        if wants_raw is not None:
            invalid_fields["wants_to_tell"] = repr(wants_raw)[:80]
        wants_raw = []
    wants: list[dict] = []
    for w in wants_raw:
        if not isinstance(w, dict):
            continue
        to = w.get("to")
        message = w.get("message")
        if to in suspect_ids and to != self_id and isinstance(message, str) and message.strip():
            wants.append({"to": to, "message": message.strip()})

    tell = raw.get("tell")
    tell = tell.strip() if isinstance(tell, str) else ""

    if invalid_fields:
        events.append({"kind": "invalid_output", "detail": {"fields": invalid_fields}})

    clean = {
        "spoken": spoken, "internal_reasoning": reasoning, "honesty": honesty, "emotion": emotion,
        "stress_delta": delta, "reveals": reveals, "accuses": accuses, "wants_to_tell": wants, "tell": tell,
    }
    return clean, events


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


# ----------------------------------------------------------------------------- the Director

class Director:
    def __init__(
        self,
        case: dict,
        world: dict,
        *,
        performer: Callable[[dict], Awaitable[dict] | dict],
        guard: Callable[[str, list], Awaitable[dict] | dict],
        rng: random.Random | None,
        difficulty: str,
        offscreen_every: int,
        fallback_lines: dict[str, str] | None,
        fallback_performer: Callable[[dict], Awaitable[dict] | dict] | None = None,
    ) -> None:
        self.case = case
        self.world = world
        self.performer = self._as_callable(performer)
        self.fallback_performer = self._as_callable(fallback_performer) if fallback_performer is not None else None
        self.guard = guard
        self.rng = rng if rng is not None else random.Random()
        self.difficulty = difficulty or world.get("game", {}).get("difficulty") or "detective"
        self.offscreen_every = int(offscreen_every or 3)
        self.fallback_lines = dict(fallback_lines or {})
        self.suspects: dict[str, dict] = {s["id"]: s for s in case.get("suspects", [])}
        self.suspect_ids: list[str] = list(self.suspects)
        self.cast_names: dict[str, str] = {sid: s.get("name", sid) for sid, s in self.suspects.items()}
        self.evidence: dict[str, dict] = world_mod.evidence_index(case)
        self.locations: dict[str, dict] = world_mod.location_index(case)
        game = self.world.setdefault("game", {})
        game.setdefault("difficulty", self.difficulty)
        for key, default in (("searched_locations", []), ("fired_framing_actions", []), ("offscreen_ticks", 0),
                             ("tactics_used", {}), ("composure_samples", []), ("turn", 0),
                             ("clock_minutes", world_mod.CLOCK_START_MINUTES), ("status", "briefing")):
            game.setdefault(key, copy.deepcopy(default))
        for sid, suspect in self.suspects.items():
            if sid not in self.world.setdefault("suspects", {}):
                self.world["suspects"][sid] = world_mod.initial_suspect_state(case, suspect)

    # ------------------------------------------------------------------ small helpers

    @staticmethod
    def _as_callable(obj: Any) -> Callable[[dict], Any]:
        if callable(obj):
            return obj
        if hasattr(obj, "perform") and callable(obj.perform):
            return obj.perform
        raise TypeError("performer must be callable or expose .perform(ctx)")

    @property
    def game(self) -> dict:
        return self.world["game"]

    @property
    def turn(self) -> int:
        return int(self.game.get("turn", 0))

    @property
    def clock(self) -> str:
        return world_mod.clock_str(self.game.get("clock_minutes", 0))

    def _state(self, sid: str) -> dict:
        return self.world["suspects"][sid]

    def _suspect(self, sid: Any) -> dict:
        if not isinstance(sid, str) or sid not in self.suspects:
            raise DirectorError(f"unknown suspect {sid!r}")
        return self.suspects[sid]

    def _ensure_open(self) -> None:
        if self.game.get("status") == "closed":
            raise GameClosed("the game is closed")

    def begin(self) -> None:
        """Move from briefing to investigating (player actions do this implicitly)."""
        if self.game.get("status") == "briefing":
            self.game["status"] = "investigating"

    def _begin_turn(self, clock_cost: int) -> int:
        self._ensure_open()
        self.begin()
        self.game["turn"] = self.turn + 1
        world_mod.advance_clock(self.world, clock_cost)
        self._expire_silences()
        return self.turn

    def _expire_silences(self, *, end_of_turn: bool = False) -> None:
        """Drop a lapsed silence. At the start of a turn a silence is over once turn > silenced_until; at the end
        of a turn it is over once this turn *was* its last (turn >= silenced_until), so the public ``silenced``
        flag is already false when the next action is offered."""
        for state in self.world["suspects"].values():
            until = state.get("silenced_until")
            if until is None:
                continue
            if self.turn > int(until) or (end_of_turn and self.turn >= int(until)):
                state["silenced_until"] = None

    def _is_silenced(self, sid: str) -> bool:
        until = self._state(sid).get("silenced_until")
        return until is not None and self.turn <= int(until)

    def _record_signal(self, signal: dict | None) -> None:
        if not signal:
            return
        composure = signal.get("composure", "neutral")
        self.game.setdefault("composure_samples", []).append(COMPOSURE_SAMPLE.get(composure, 0.5))

    def _count_action(self, key: str) -> None:
        used = self.game.setdefault("tactics_used", {})
        used[key] = int(used.get(key, 0)) + 1

    def _new_outcome(self) -> dict:
        return {"public_turns": [], "private_turns": [], "guard_events": [], "world_events": [], "tickers": [],
                "offscreen": None, "watson_visible": None, "clock": self.clock}

    def _stress_pct(self, sid: str) -> int:
        return stress_mod.stress_pct(self.suspects[sid], self._state(sid))

    def _tell_for(self, sid: str, clean: dict) -> str:
        if clean.get("tell"):
            return clean["tell"]
        tells = self.suspects[sid].get("tells") or {}
        if clean.get("reveals"):
            return tells.get("cracking", "")
        emotion = clean.get("emotion")
        if emotion in ("nervous", "afraid", "sad"):
            return tells.get("nervous", "")
        if emotion == "angry":
            return tells.get("angry", "")
        return ""

    def _locked_ids(self, sid: str) -> list[str]:
        return stress_mod.locked_secret_ids(self.suspects[sid], self._state(sid))

    def _locked_secrets(self, sid: str, locked_ids: list[str]) -> list[dict]:
        locked = set(locked_ids)
        return [
            {"id": s["id"], "text": s.get("text", ""), "key_phrases": s.get("key_phrases", "")}
            for s in self.suspects[sid].get("secrets", []) if s["id"] in locked
        ]

    def cast_public(self) -> list[dict]:
        from .public import public_cast
        return public_cast(self.case, self.world)

    # ------------------------------------------------------------------ perform context + guard loop

    def _perform_context(
        self,
        sid: str,
        user_message: str,
        turn_type: str,
        *,
        tactic: str | None = None,
        evidence: dict | None = None,
        player_signal: dict | None = None,
        confrontation_with: dict | None = None,
    ) -> dict:
        """INTERFACES §3 PerformContext for exactly one suspect. Contains nothing about anyone else beyond
        public names/ids. The suspect dict and state are deep-copied so the performer cannot mutate the world."""
        state = self._state(sid)
        unlocked = stress_mod.recompute_unlocks(self.case, self.world, sid)
        locked = self._locked_ids(sid)
        return {
            "case": {"title": self.case.get("title", ""), "setting": self.case.get("setting", "")},
            "suspect": copy.deepcopy(self.suspects[sid]),
            "state": copy.deepcopy(state),
            "unlocked": list(unlocked),
            "locked": list(locked),
            "user_message": user_message,
            "turn_type": turn_type,
            "tactic": tactic,
            "evidence": copy.deepcopy(evidence) if evidence else None,
            "player_signal": copy.deepcopy(player_signal) if player_signal else None,
            "confrontation_with": dict(confrontation_with) if confrontation_with else None,
            "retry_ids": [],
            "difficulty": self.difficulty,
            "suspect_ids": list(self.suspect_ids),
            "cast_names": dict(self.cast_names),
        }

    def _guard_event(self, sid: str, seq: int, kind: str, detail: dict) -> dict:
        return {"turn": self.turn, "seq": seq, "suspect_id": sid, "kind": kind, "detail": detail}

    def _fallback_output(self, sid: str, previous: dict | None) -> dict:
        line = self.fallback_lines.get(sid) or DEFAULT_FALLBACK_LINE
        base = dict(previous) if previous else empty_output()
        base.update({"spoken": line, "honesty": "evasive", "reveals": [], "wants_to_tell": []})
        if not previous:
            base["emotion"] = "nervous"
        base["tell"] = base.get("tell") or ""
        return base

    async def _call_performer(self, ctx: dict, sid: str, seq: int, events: list[dict]) -> dict | None:
        """Call the performer; on LLMUnavailable use the fallback performer (event ``llm_fallback_scripted``);
        on InvalidOutput retry once. Returns None when the canned fallback line must be used."""
        for attempt in (1, 2):
            try:
                return await _maybe_await(self.performer(ctx))
            except Exception as exc:
                name = type(exc).__name__
                if name == "LLMUnavailable":
                    events.append(self._guard_event(sid, seq, "llm_fallback_scripted", {
                        "error": str(exc)[:300], "fallback_performer": self.fallback_performer is not None}))
                    if self.fallback_performer is None:
                        return None
                    try:
                        return await _maybe_await(self.fallback_performer(ctx))
                    except Exception as exc2:  # noqa: BLE001
                        events.append(self._guard_event(sid, seq, "invalid_output", {
                            "reason": "fallback performer failed", "error": str(exc2)[:300]}))
                        return None
                if name == "InvalidOutput":
                    events.append(self._guard_event(sid, seq, "invalid_output", {
                        "reason": "performer raised InvalidOutput", "error": str(exc)[:300], "retry": attempt == 1}))
                    if attempt == 1:
                        continue
                    return None
                raise
        return None

    async def _perform_guarded(self, sid: str, ctx: dict, events: list[dict], seq: int = 1) -> tuple[dict, int]:
        """perform → validate → guard → (retry with retry_ids up to 2×) → fallback line. Returns (clean, latency_ms)."""
        locked_secrets = self._locked_secrets(sid, ctx["locked"])
        locked_ids = set(ctx["locked"])
        started = time.perf_counter()
        clean: dict | None = None
        leak_retries = 0
        empty_retry_done = False
        system_blocks: list[str] | None = None
        while True:
            raw = await self._call_performer(ctx, sid, seq, events)
            if isinstance(ctx.get("system_blocks"), list):
                system_blocks = [str(b) for b in ctx["system_blocks"]]
            if raw is None:
                clean = self._fallback_output(sid, clean)
                break
            clean, v_events = validate_output(raw, ctx)
            for ev in v_events:
                events.append(self._guard_event(sid, seq, ev["kind"], ev["detail"]))
            if not clean["spoken"]:
                if not empty_retry_done:
                    empty_retry_done = True
                    events.append(self._guard_event(sid, seq, "invalid_output", {"reason": "empty spoken", "retry": True}))
                    continue
                events.append(self._guard_event(sid, seq, "invalid_output", {"reason": "empty spoken", "fallback": True}))
                clean = self._fallback_output(sid, clean)
                break
            if not locked_secrets:
                break
            verdict = await _maybe_await(self.guard(clean["spoken"], copy.deepcopy(locked_secrets)))
            verdict = verdict if isinstance(verdict, dict) else {}
            leaked = [x for x in (verdict.get("leaked") or []) if isinstance(x, str) and x in locked_ids]
            if not leaked:
                break
            reason = str(verdict.get("reason") or "")
            if leak_retries < MAX_LEAK_RETRIES:
                leak_retries += 1
                events.append(self._guard_event(sid, seq, "leak_regenerated", {
                    "leaked": leaked, "reason": reason, "attempt": leak_retries, "spoken": clean["spoken"]}))
                ctx["retry_ids"] = list(leaked)
                continue
            events.append(self._guard_event(sid, seq, "leak_fallback", {
                "leaked": leaked, "reason": reason, "spoken": clean["spoken"]}))
            clean = self._fallback_output(sid, clean)
            break
        latency_ms = int((time.perf_counter() - started) * 1000)
        if system_blocks is not None:
            self._state(sid)["last_system_blocks"] = system_blocks
        assert clean is not None
        return clean, latency_ms

    # ------------------------------------------------------------------ state application

    def _append_conversation(self, sid: str, user_message: str | None, spoken: str | None) -> None:
        conv = self._state(sid).setdefault("conversation", [])
        if user_message:
            conv.append({"role": "user", "content": user_message})
        if spoken is not None:
            conv.append({"role": "assistant", "content": spoken})

    def _apply_output(self, sid: str, clean: dict, user_message: str) -> None:
        """Conversation, emotion/tell, last_* fields, revealed (validated reveals), outbox (wants_to_tell)."""
        state = self._state(sid)
        self._append_conversation(sid, user_message, clean["spoken"])
        state["emotion"] = clean["emotion"]
        state["tell"] = self._tell_for(sid, clean)
        state["last_internal_reasoning"] = clean["internal_reasoning"]
        state["last_honesty"] = clean["honesty"]
        state["last_accuses"] = clean["accuses"]
        revealed = state.setdefault("revealed_secret_ids", [])
        for r in clean["reveals"]:
            if r not in revealed:
                revealed.append(r)
        social.queue_wants_to_tell(self.case, self.world, sid, clean["wants_to_tell"], self.turn)

    def _private_row(self, *, seq: int, type: str, actor: str, target: str | None, input: Any, output: Any,
                     stress_before: int | None = None, stress_after: int | None = None,
                     latency_ms: int | None = None) -> dict:
        return {"turn": self.turn, "seq": seq, "type": type, "actor": actor, "target": target, "input": input,
                "output": output, "stress_before": stress_before, "stress_after": stress_after,
                "latency_ms": latency_ms}

    def _after_player_turn(self, outcome: dict, addressed: set[str], seq: int) -> int:
        """Decay, framing actions, off-screen tick, lapsed silences. Returns the next free seq."""
        stress_mod.apply_decay(self.world, addressed)
        self._expire_silences(end_of_turn=True)
        for fired in world_mod.evaluate_framing_actions(self.case, self.world, self.rng):
            outcome["private_turns"].append(self._private_row(
                seq=seq, type="world", actor="director", target=fired["suspect_id"], input=None, output=fired))
            seq += 1
            outcome["world_events"].append({"text": fired.get("ticker", ""), "evidence": fired.get("evidence")})
            if fired.get("ticker"):
                outcome["tickers"].append(fired["ticker"])
        if social.should_tick(self.turn, self.difficulty, self.offscreen_every):
            dropped: list[dict] = []
            deliveries = social.run_offscreen_tick(self.case, self.world, self.rng, dropped=dropped)
            ticker = social.pick_ticker(self.case, self.rng)
            payload = {"deliveries": deliveries, "dropped": dropped, "ticker": ticker}
            outcome["private_turns"].append(self._private_row(
                seq=seq, type="offscreen", actor="director", target=None, input=None, output=payload))
            seq += 1
            outcome["offscreen"] = payload
            if ticker:
                outcome["tickers"].append(ticker)
        outcome["clock"] = self.clock
        return seq

    # ------------------------------------------------------------------ player turn: ask | tactic | present

    async def player_turn(self, req: dict) -> dict:
        self._ensure_open()
        if not isinstance(req, dict):
            raise DirectorError("request must be an object")
        ttype = req.get("type")
        if ttype not in PLAYER_TURN_TYPES:
            raise DirectorError(f"unsupported turn type {ttype!r}")
        sid = req.get("suspect_id")
        suspect = self._suspect(sid)
        text = str(req.get("text") or "").strip()
        tactic: str | None = None
        evidence: dict | None = None
        if ttype == "ask" and not text:
            raise DirectorError("ask requires text")
        if ttype == "tactic":
            tactic = req.get("tactic")
            if tactic not in TACTICS:
                raise DirectorError(f"unknown tactic {tactic!r}")
        if ttype == "present":
            eid = req.get("evidence_id")
            evidence = self.evidence.get(eid) if isinstance(eid, str) else None
            if evidence is None:
                raise DirectorError(f"unknown evidence {eid!r}")
            if not world_mod.is_presentable(self.world, eid):
                raise DirectorError(f"evidence {eid!r} is not in the detective's possession")
        signal = normalize_player_signal(req.get("player_signal"))

        self._begin_turn(world_mod.CLOCK_COST[ttype])
        turn = self.turn
        self._record_signal(signal)
        self._count_action(tactic if ttype == "tactic" else ttype)
        state = self._state(sid)
        if tactic == "flatter":
            state["flatter_count"] = int(state.get("flatter_count", 0)) + 1
        elif tactic == "threaten":
            state["threaten_count"] = int(state.get("threaten_count", 0)) + 1

        outcome = self._new_outcome()
        guard_events: list[dict] = outcome["guard_events"]
        stress_before = int(state.get("stress", 0))

        if ttype == "present":
            evidence_text = world_mod.evidence_text_for_present(self.case, self.world, evidence["id"])
            user_message = format_user_message("present", text=text, evidence_name=evidence.get("name", evidence["id"]),
                                               evidence_text=evidence_text)
            detective_text = text or None
        elif ttype == "tactic":
            user_message = format_user_message("tactic", text=text, tactic=tactic)
            detective_text = None if tactic == "silence" else (text or DEFAULT_TACTIC_TEXT.get(tactic))
        else:
            user_message = format_user_message("ask", text=text)
            detective_text = text

        latency_ms: int | None = None
        performed = False
        shutdown_rules = suspect.get("shutdown_rules") or {}
        if ttype == "tactic" and tactic in shutdown_rules:
            # §8.4 shutdown: no performer call.
            line = str(shutdown_rules[tactic])
            state["stress"] = int(state.get("stress", 0)) + SHUTDOWN_STRESS
            state["silenced_until"] = turn + SILENCE_TURNS
            clean = empty_output(line, honesty="evasive", emotion="afraid", stress_delta=SHUTDOWN_STRESS,
                                 internal_reasoning="(shutdown rule: refuses to cooperate)")
            clean["tell"] = (suspect.get("tells") or {}).get("nervous", "")
            self._apply_output(sid, clean, user_message)
            stress_mod.recompute_unlocks(self.case, self.world, sid)
        elif ttype in ("ask", "tactic") and self._is_silenced(sid):
            # §8.4 silence: "…" + the shutdown line, no call, no stress change.
            line = self._silence_line(suspect, tactic)
            clean = empty_output(f"… {line}".strip(), honesty="evasive", emotion=state.get("emotion") or "afraid",
                                 stress_delta=0, internal_reasoning="(silenced: will not cooperate)")
            clean["tell"] = (suspect.get("tells") or {}).get("nervous", "")
            self._apply_output(sid, clean, user_message)
        else:
            if ttype == "present":
                state["silenced_until"] = None  # presenting evidence ends a silence early
            evidence_ctx = None
            points_to_self: bool | None = None
            if ttype == "present":
                points_to_self = sid in (evidence.get("points_to") or [])
                evidence_ctx = {"id": evidence["id"], "name": evidence.get("name", evidence["id"]),
                                "text": world_mod.evidence_text_for_present(self.case, self.world, evidence["id"]),
                                "points_to_self": points_to_self}
            ctx = self._perform_context(sid, user_message, ttype, tactic=tactic, evidence=evidence_ctx,
                                        player_signal=signal)
            clean, latency_ms = await self._perform_guarded(sid, ctx, guard_events, seq=1)
            performed = True
            delta = stress_mod.compute_delta(
                clean["stress_delta"], tactic=tactic, evidence_points_to_self=points_to_self,
                sensitivity=suspect.get("stress_sensitivity") or {},
                composure=(signal or {}).get("composure"), difficulty=self.difficulty,
            )
            stress_mod.apply_delta(self.world, sid, delta)
            self._apply_output(sid, clean, user_message)
            stress_mod.recompute_unlocks(self.case, self.world, sid)

        if ttype == "present":
            state["last_seen_location"] = evidence.get("location") or state.get("last_seen_location", "")
        stress_after = int(state.get("stress", 0))

        row_input = {"type": ttype, "suspect_id": sid, "text": text or None, "tactic": tactic,
                     "evidence_id": evidence["id"] if evidence else None, "player_signal": signal,
                     "user_message": user_message, "detective_text": detective_text, "performed": performed}
        outcome["private_turns"].append(self._private_row(
            seq=1, type=ttype, actor=sid, target=sid, input=row_input, output=clean,
            stress_before=stress_before, stress_after=stress_after, latency_ms=latency_ms))
        outcome["public_turns"].append(public_turn(
            turn=turn, seq=1, type=ttype, actor=sid, target=sid, clock=self.clock, detective_text=detective_text,
            tactic=tactic, evidence_id=evidence["id"] if evidence else None, spoken=clean["spoken"],
            tell=state.get("tell") or "", emotion=state.get("emotion") or "neutral", stress_pct=self._stress_pct(sid)))
        self._after_player_turn(outcome, {sid}, seq=2)
        outcome["watson_visible"] = {
            "turn": turn, "type": ttype, "target": sid, "detective_text": detective_text, "spoken": clean["spoken"],
            "tactic": tactic, "evidence_id": evidence["id"] if evidence else None,
        }
        return outcome

    def _silence_line(self, suspect: dict, tactic: str | None) -> str:
        rules = suspect.get("shutdown_rules") or {}
        if tactic and tactic in rules:
            return str(rules[tactic])
        for line in rules.values():
            return str(line)
        return ""

    # ------------------------------------------------------------------ confrontation

    async def confront(self, req: dict, on_line=None, get_interject=None) -> dict:
        self._ensure_open()
        if not isinstance(req, dict):
            raise DirectorError("request must be an object")
        a, b = req.get("a"), req.get("b")
        self._suspect(a)
        self._suspect(b)
        if a == b:
            raise DirectorError("a confrontation needs two different suspects")
        topic = str(req.get("topic") or "").strip()
        if not topic:
            raise DirectorError("confront requires a topic")
        try:
            rounds = int(req.get("rounds") or DEFAULT_ROUNDS)
        except (TypeError, ValueError):
            rounds = DEFAULT_ROUNDS
        rounds = int(stress_mod.clamp(rounds, 1, MAX_ROUNDS))
        signal = normalize_player_signal(req.get("player_signal"))
        req_interject = str(req.get("interject") or "").strip() or None

        self._begin_turn(world_mod.CLOCK_COST["confront"])
        turn = self.turn
        self._record_signal(signal)
        self._count_action("confront")
        outcome = self._new_outcome()
        guard_events: list[dict] = outcome["guard_events"]
        names = self.cast_names
        pending: dict[str, list[str]] = {a: [format_user_message("interject", text=topic)], b: []}
        transcript: list[dict] = []
        seq = 0

        async def emit(pub: dict) -> None:
            outcome["public_turns"].append(pub)
            if on_line is not None:
                await _maybe_await(on_line(pub))

        async def speak(speaker: str, listener: str, round_no: int) -> None:
            nonlocal seq
            seq += 1
            user_message = "\n".join(pending[speaker])
            pending[speaker] = []
            st = self._state(speaker)
            before = int(st.get("stress", 0))
            ctx = self._perform_context(speaker, user_message, "confront", player_signal=signal,
                                        confrontation_with={"id": listener, "name": names[listener]})
            clean, latency_ms = await self._perform_guarded(speaker, ctx, guard_events, seq=seq)
            delta = stress_mod.compute_delta(
                clean["stress_delta"], tactic=None, evidence_points_to_self=None,
                sensitivity=self.suspects[speaker].get("stress_sensitivity") or {},
                composure=(signal or {}).get("composure"), difficulty=self.difficulty)
            stress_mod.apply_delta(self.world, speaker, delta)
            self._apply_output(speaker, clean, user_message)
            stress_mod.recompute_unlocks(self.case, self.world, speaker)
            accused_bonus = False
            if clean["accuses"] == listener:
                stress_mod.apply_delta(self.world, listener, CONFRONT_ACCUSED_STRESS)
                stress_mod.recompute_unlocks(self.case, self.world, listener)
                accused_bonus = True
            social.add_heard(self.world, listener, speaker, clean["spoken"], turn, "confrontation")
            pending[listener].append(format_user_message("confront", speaker_name=names[speaker], spoken=clean["spoken"]))
            after = int(st.get("stress", 0))
            detective_text = topic if seq == 1 else None
            transcript.append({"actor": speaker, "name": names[speaker], "spoken": clean["spoken"]})
            outcome["private_turns"].append(self._private_row(
                seq=seq, type="confront", actor=speaker, target=listener,
                input={"a": a, "b": b, "topic": topic, "round": round_no, "user_message": user_message,
                       "detective_text": detective_text, "player_signal": signal, "accused_bonus_to": listener if accused_bonus else None},
                output=clean, stress_before=before, stress_after=after, latency_ms=latency_ms))
            await emit(public_turn(
                turn=turn, seq=seq, type="confront", actor=speaker, target=listener, other=listener, clock=self.clock,
                detective_text=detective_text, spoken=clean["spoken"], tell=st.get("tell") or "",
                emotion=st.get("emotion") or "neutral", stress_pct=self._stress_pct(speaker)))

        async def interject(text: str, round_no: int) -> None:
            nonlocal seq
            seq += 1
            msg = format_user_message("interject", text=text)
            pending[a].append(msg)
            pending[b].append(msg)
            transcript.append({"actor": "detective", "name": "Detective", "spoken": text})
            outcome["private_turns"].append(self._private_row(
                seq=seq, type="confront", actor="detective", target=None,
                input={"a": a, "b": b, "topic": topic, "round": round_no, "interject": text, "detective_text": text},
                output=None))
            await emit(public_turn(turn=turn, seq=seq, type="confront", actor="detective", target=None,
                                   clock=self.clock, detective_text=text))

        for round_no in range(1, rounds + 1):
            await speak(a, b, round_no)
            await speak(b, a, round_no)
            if round_no < rounds:
                text: Any = None
                if get_interject is not None:
                    text = await _maybe_await(get_interject())
                elif req_interject and round_no == 1:
                    text = req_interject
                if isinstance(text, str) and text.strip():
                    await interject(text.strip(), round_no)

        # Whatever was heard last but not yet answered still belongs in that suspect's own transcript.
        for sid in (a, b):
            for msg in pending[sid]:
                self._append_conversation(sid, msg, None)
            pending[sid] = []

        self._after_player_turn(outcome, {a, b}, seq=seq + 1)
        outcome["watson_visible"] = {
            "turn": turn, "type": "confront", "target": [a, b], "detective_text": topic,
            "spoken": "\n".join(f"{t['name']}: {t['spoken']}" for t in transcript),
            "tactic": None, "evidence_id": None, "lines": transcript,
        }
        return outcome

    # ------------------------------------------------------------------ search

    def search(self, location_id: str) -> dict:
        self._ensure_open()
        if not isinstance(location_id, str) or location_id not in self.locations:
            raise DirectorError(f"unknown location {location_id!r}")
        self._begin_turn(0)  # world.search adds the +10 itself
        turn = self.turn
        self._count_action("search")
        newly = world_mod.search(self.case, self.world, location_id)
        outcome = self._new_outcome()
        examined_public = [world_mod.public_evidence_item(self.evidence[eid], self.world["evidence"][eid]) for eid in newly]
        outcome["private_turns"].append(self._private_row(
            seq=1, type="search", actor="detective", target=location_id, input={"location_id": location_id},
            output={"examined": newly}))
        outcome["public_turns"].append(public_turn(
            turn=turn, seq=1, type="search", actor="detective", target=location_id, clock=self.clock))
        self._after_player_turn(outcome, set(), seq=2)
        outcome["search"] = {"location_id": location_id, "examined": newly, "evidence": examined_public}
        outcome["watson_visible"] = {
            "turn": turn, "type": "search", "target": location_id, "detective_text": None, "spoken": None,
            "tactic": None, "evidence_id": None,
            "examined_evidence": [{"id": e["id"], "name": e["name"], "examined_detail": e.get("examined_detail", "")}
                                  for e in examined_public],
        }
        return outcome

    # ------------------------------------------------------------------ accuse

    async def accuse(self, req: dict, motive_points: int) -> dict:
        self._ensure_open()
        if not isinstance(req, dict):
            raise DirectorError("request must be an object")
        sid = req.get("suspect_id")
        self._suspect(sid)
        method_ids = [e for e in (req.get("method_evidence_ids") or []) if isinstance(e, str)]
        motive_text = str(req.get("motive_text") or "")
        try:
            confidence = float(req.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = float(stress_mod.clamp(confidence, 0.0, 1.0))
        self.begin()
        self.game["turn"] = self.turn + 1
        turn = self.turn
        result = scoring.score(self.case, sid, method_ids, motive_points)
        solution = self.case.get("solution") or {}
        accusation = {
            "suspect_id": sid,
            "method_evidence_ids": method_ids,
            "motive_text": motive_text,
            "confidence": confidence,
            "motive_points": result["motive"],
            "score": result,
            "correct": sid == solution.get("murderer"),
            "rank": scoring.rank(result["total"]),
            "confidence_badge": scoring.confidence_badge(confidence),
            "turn": turn,
        }
        self.game["status"] = "closed"
        outcome = self._new_outcome()
        outcome["private_turns"].append(self._private_row(
            seq=1, type="accuse", actor="detective", target=sid,
            input={"suspect_id": sid, "method_evidence_ids": method_ids, "motive_text": motive_text,
                   "confidence": confidence},
            output={"score": result, "correct": accusation["correct"], "rank": accusation["rank"],
                    "motive_points": result["motive"]}))
        outcome["public_turns"].append(public_turn(
            turn=turn, seq=1, type="accuse", actor="detective", target=sid, clock=self.clock))
        outcome["accusation"] = accusation
        outcome["clock"] = self.clock
        return outcome
