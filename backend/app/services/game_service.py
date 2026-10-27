"""The app layer between HTTP/WS and the Director (docs/INTERFACES.md §4).

Each game has a ``GameRuntime`` holding its last *committed* world. An action runs the Director on a deep copy, writes
the turn rows, the snapshot, guard events and the state projection in one transaction, and only then adopts the copy.
A failed action leaves the committed world untouched, and readers (GET, /debug) never see a half-applied turn.
One asyncio.Lock per game serialises actions.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import pathlib
import random
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import BackgroundTasks, WebSocket
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..agents import judge, leak_guard, watson
from ..agents.checker import static_check
from ..agents.client import models_summary, resolve_mode
from ..agents.performer import get_scripted_performer
from ..agents.suspect import GeminiPerformer
from ..config import Settings
from ..engine import debrief as debrief_mod
from ..engine import snapshot
from ..engine import world as world_mod
from ..engine.director import Director, DirectorError
from ..engine.public import public_cast, public_locations
from ..models import (
    AccusationRow,
    CaseRow,
    EvidenceStateRow,
    GameRow,
    GuardrailEventRow,
    NotebookEntryRow,
    SuspectStateRow,
    TurnRow,
)

log = logging.getLogger("alibi.game_service")


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


_PRESETS = (
    ("manor", ("manor", "hall", "country house")),
    ("liner", ("liner", "ship", "sea", "deck", "rms")),
    ("startup", ("startup", "office", "pitch")),
    ("dorm", ("dorm", "campus", "college", "cornell", "ithaca")),
)
_SUSPECT_COLUMNS = (
    "stress", "unlocked_secret_ids", "revealed_secret_ids", "heard_log", "outbox", "flatter_count", "threaten_count",
    "silenced_until", "emotion", "last_seen_location", "conversation",
)
_WATSON_TURN_KEYS = ("turn", "seq", "type", "actor", "target", "detective_text", "spoken", "tactic", "evidence_id")
TICKER_KEEP = 8


def preset(setting: str) -> str:
    s = setting.lower()
    return next((name for name, words in _PRESETS if any(w in s for w in words)), "other")


def _game_case(case: dict) -> dict:
    v = case.get("victim") or {}
    return {"id": case["id"], "title": case["title"], "setting": case["setting"], "briefing": case["briefing"],
            "victim": {"name": v.get("name", ""), "description": v.get("description", ""),
                       "cause_of_death_public": v.get("cause_of_death_public", "")},
            "timeline_public": case.get("timeline_public", [])}


def _tickers(rows: list[dict]) -> list[str]:
    return [r["output"]["ticker"] for r in rows
            if r["type"] in ("world", "offscreen") and (r.get("output") or {}).get("ticker")]


def _row_dict(r: TurnRow) -> dict:
    return {"turn": r.turn, "seq": r.seq, "type": r.type, "actor": r.actor, "target": r.target, "input": r.input,
            "output": r.output, "public": r.public, "stress_before": r.stress_before, "stress_after": r.stress_after,
            "snapshot": r.snapshot, "latency_ms": r.latency_ms, "clock": (r.public or {}).get("clock")}


def cross_contamination(case: dict, world: dict) -> list[dict]:
    """Another suspect's secret id (as Block A lists it) or secret text inside a suspect's last system blocks."""
    found = []
    for suspect in case["suspects"]:
        blocks = "\n".join(world["suspects"][suspect["id"]].get("last_system_blocks") or [])
        if not blocks:
            continue
        for other in case["suspects"]:
            if other["id"] == suspect["id"]:
                continue
            for sec in other.get("secrets", []):
                if f"[{sec['id']}]" in blocks or (sec.get("text") and sec["text"] in blocks):
                    found.append({"suspect_id": suspect["id"], "found": f"{other['id']}:{sec['id']}"})
    return found


class Hub:
    """WebSocket fan-out per game, in the canonical ``{type, data}`` envelope frontend/src/api/ws.ts expects."""

    def __init__(self) -> None:
        self._sockets: dict[str, set[WebSocket]] = defaultdict(set)

    def add(self, game_id: str, ws: WebSocket) -> None:
        self._sockets[game_id].add(ws)

    def remove(self, game_id: str, ws: WebSocket) -> None:
        self._sockets[game_id].discard(ws)

    async def send(self, game_id: str, type_: str, data: Any) -> None:
        for ws in list(self._sockets.get(game_id, ())):
            try:
                await ws.send_json({"type": type_, "data": data})
            except Exception:  # noqa: BLE001 - a dead socket must not fail the turn
                self._sockets[game_id].discard(ws)


@dataclass
class GameRuntime:
    """Committed state of one game. Replaced only under ``lock`` and only after the DB commit."""

    game_id: str
    case_id: str
    case: dict
    difficulty: str
    accessibility: dict
    fallback_lines: dict
    world: dict
    public_turns: list[dict]
    tickers: list[str]
    snapshot_turns: list[int]
    notebook: dict | None
    branch: int = 0
    interject: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def rewind_to(self, fresh: GameRuntime) -> None:
        self.world, self.public_turns, self.tickers = fresh.world, fresh.public_turns, fresh.tickers
        self.snapshot_turns, self.notebook = fresh.snapshot_turns, fresh.notebook
        self.branch += 1
        self.interject = None


class GameService:
    def __init__(self, settings: Settings, sessions: async_sessionmaker, hub: Hub) -> None:
        self.settings = settings
        self.sessions = sessions
        self.hub = hub
        self._runtimes: dict[str, GameRuntime] = {}
        self._loading = asyncio.Lock()
        self._gemini = GeminiPerformer()
        self._scripted = get_scripted_performer()

    # ------------------------------------------------------------------ LLM wiring

    def llm_mode(self) -> str:
        return resolve_mode({"llm_mode": self.settings.llm_mode, "fake_llm": self.settings.fake_llm})

    def models(self) -> dict[str, str]:
        return models_summary()

    async def _perform(self, ctx: dict) -> dict:
        performer = self._gemini if self.llm_mode() == "gemini" else self._scripted
        return await performer.perform(ctx)

    async def _guard(self, spoken: str, locked: list[dict]) -> dict:
        return await leak_guard.check(spoken, locked, self.llm_mode())

    def _director(self, rt: GameRuntime, world: dict) -> Director:
        # Seeded from the coming turn so a restarted server rolls framing actions exactly as one that never stopped.
        seed = f"{self.settings.rng_seed or rt.game_id}:{world['game']['turn'] + 1}"
        return Director(rt.case, world, performer=self._perform, guard=self._guard, rng=random.Random(seed),
                        difficulty=rt.difficulty, offscreen_every=self.settings.offscreen_every,
                        fallback_lines=rt.fallback_lines, fallback_performer=self._scripted.perform)

    # ------------------------------------------------------------------ cases

    async def sync_case_files(self, directory: pathlib.Path) -> None:
        """Insert every valid cases/*.json whose id is not in the DB yet; invalid files are logged and skipped."""
        async with self.sessions.begin() as s:
            known = set(await s.scalars(select(CaseRow.id)))
            for path in sorted(directory.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    log.error("skipping case file %s: %s", path.name, exc)
                    continue
                errors = self._case_errors(data)
                if errors:
                    log.error("skipping case file %s: %s", path.name, "; ".join(errors[:5]))
                    continue
                if data["id"] not in known:
                    s.add(self._case_row(data, slug=path.stem))
                    known.add(data["id"])

    @staticmethod
    def _case_errors(data: Any) -> list[str]:
        if not isinstance(data, dict):
            return ["a case must be a JSON object"]
        missing = [k for k in ("id", "title", "setting", "briefing") if not isinstance(data.get(k), str) or not data[k]]
        return [f"missing top-level key {k}" for k in missing] + static_check(data)

    @staticmethod
    def _case_row(data: dict, *, slug: str) -> CaseRow:
        return CaseRow(id=data["id"], slug=slug, title=data["title"], setting=data["setting"], data=data,
                       generated=bool(data.get("generated")), checker_report=None)

    async def case_count(self) -> int:
        async with self.sessions() as s:
            return int(await s.scalar(select(func.count()).select_from(CaseRow)) or 0)

    async def list_cases(self) -> list[dict]:
        async with self.sessions() as s:
            rows = (await s.scalars(select(CaseRow).order_by(CaseRow.created_at, CaseRow.id))).all()
        return [{"id": r.id, "title": r.title, "setting": r.setting, "generated": r.generated,
                 "n_suspects": len(r.data.get("suspects", [])), "preset": preset(r.setting)} for r in rows]

    async def get_case(self, case_id: str) -> dict:
        async with self.sessions() as s:
            row = await s.get(CaseRow, case_id)
        if row is None:
            raise NotFound(f"unknown case {case_id!r}")
        return row.data

    async def import_case(self, data: Any) -> str:
        errors = self._case_errors(data)
        if errors:
            raise BadRequest("case failed validation: " + "; ".join(errors[:8]))
        async with self.sessions.begin() as s:
            existing = await s.get(CaseRow, data["id"])
            if existing is not None:
                if existing.data == data:
                    return existing.id
                data = {**data, "id": f"{data['id']}_{uuid.uuid4().hex[:6]}"}
            s.add(self._case_row(data, slug=data["id"]))
        return data["id"]

    # ------------------------------------------------------------------ loading

    async def runtime(self, game_id: str) -> GameRuntime:
        rt = self._runtimes.get(game_id)
        if rt is None:
            async with self._loading:
                rt = self._runtimes.get(game_id)
                if rt is None:
                    async with self.sessions() as s:
                        rt = await self._read_runtime(s, game_id)
                    self._runtimes[game_id] = rt
        return rt

    @staticmethod
    async def _turn_rows(s: AsyncSession, game_id: str) -> list[TurnRow]:
        q = (select(TurnRow).where(TurnRow.game_id == game_id, TurnRow.archived.is_(False))
             .order_by(TurnRow.turn, TurnRow.seq))
        return list((await s.scalars(q)).all())

    @staticmethod
    async def _guard_rows(s: AsyncSession, game_id: str) -> list[dict]:
        q = (select(GuardrailEventRow)
             .where(GuardrailEventRow.game_id == game_id, GuardrailEventRow.archived.is_(False))
             .order_by(GuardrailEventRow.turn, GuardrailEventRow.seq, GuardrailEventRow.created_at))
        return [{"turn": g.turn, "seq": g.seq, "suspect_id": g.suspect_id, "kind": g.kind, "detail": g.detail}
                for g in (await s.scalars(q)).all()]

    async def _read_runtime(self, s: AsyncSession, game_id: str) -> GameRuntime:
        game = await s.get(GameRow, game_id)
        if game is None:
            raise NotFound(f"unknown game {game_id!r}")
        case = (await s.get(CaseRow, game.case_id)).data
        rows = [_row_dict(r) for r in await self._turn_rows(s, game_id)]
        notebook = await s.scalar(
            select(NotebookEntryRow.data)
            .where(NotebookEntryRow.game_id == game_id, NotebookEntryRow.archived.is_(False))
            .order_by(NotebookEntryRow.turn.desc(), NotebookEntryRow.created_at.desc()).limit(1))
        snaps = [r for r in rows if r["snapshot"] is not None]
        world = snapshot.restore(snaps[-1]["snapshot"]) if snaps else world_mod.initial_world(case, game.difficulty)
        return GameRuntime(
            game_id=game_id, case_id=game.case_id, case=case, difficulty=game.difficulty,
            accessibility=game.accessibility or {}, fallback_lines=game.fallback_lines or {}, world=world,
            public_turns=[r["public"] for r in rows if r["public"]], tickers=_tickers(rows),
            snapshot_turns=[r["turn"] for r in snaps], notebook=notebook)

    # ------------------------------------------------------------------ persistence

    @staticmethod
    async def _write_projection(s: AsyncSession, game_id: str, world: dict) -> None:
        game = await s.get(GameRow, game_id)
        game.status = world["game"]["status"]
        game.turn = world["game"]["turn"]
        game.clock_minutes = world["game"]["clock_minutes"]
        suspects = {r.suspect_id: r for r in await s.scalars(
            select(SuspectStateRow).where(SuspectStateRow.game_id == game_id))}
        for sid, st in world["suspects"].items():
            row = suspects.get(sid) or SuspectStateRow(game_id=game_id, suspect_id=sid)
            s.add(row)
            for col in _SUSPECT_COLUMNS:
                setattr(row, col, st.get(col))
        evidence = {r.evidence_id: r for r in await s.scalars(
            select(EvidenceStateRow).where(EvidenceStateRow.game_id == game_id))}
        for eid, st in world["evidence"].items():
            row = evidence.get(eid) or EvidenceStateRow(game_id=game_id, evidence_id=eid)
            s.add(row)
            row.state, row.examined_turn = st["state"], st.get("examined_turn")

    async def _stage(self, s: AsyncSession, rt: GameRuntime, outcome: dict, world: dict) -> None:
        gid = rt.game_id
        rows = outcome["private_turns"]
        public = {(p["turn"], p["seq"]): p for p in outcome["public_turns"]}
        snap = snapshot.take(world)
        for i, r in enumerate(rows):
            s.add(TurnRow(
                game_id=gid, turn=r["turn"], seq=r["seq"], type=r["type"], actor=r["actor"], target=r["target"],
                input=r["input"], output=r["output"], public=public.get((r["turn"], r["seq"])),
                stress_before=r["stress_before"], stress_after=r["stress_after"], latency_ms=r["latency_ms"],
                snapshot=snap if i == len(rows) - 1 else None))
        for ev in outcome["guard_events"]:
            s.add(GuardrailEventRow(game_id=gid, turn=ev["turn"], seq=ev.get("seq"), suspect_id=ev.get("suspect_id"),
                                    kind=ev["kind"], detail=ev.get("detail")))
        await self._write_projection(s, gid, world)
        accusation = outcome.get("accusation")
        if accusation:
            await s.flush()
            rows_now = [_row_dict(r) for r in await self._turn_rows(s, gid)]
            debrief = debrief_mod.build(rt.case, world, rows_now, await self._guard_rows(s, gid), accusation,
                                        public_cast(rt.case, world), game_id=gid)
            s.add(AccusationRow(
                game_id=gid, turn=accusation["turn"], suspect_id=accusation["suspect_id"],
                method_evidence_ids=accusation["method_evidence_ids"], motive_text=accusation["motive_text"],
                confidence=accusation["confidence"], score=accusation["score"], correct=accusation["correct"],
                rank=accusation["rank"], debrief=debrief))

    async def _run(self, rt: GameRuntime, action: Callable[[Director], Awaitable[dict] | dict]) -> dict:
        """Run one Director action on a copy of the committed world, persist it, then adopt it. Caller holds rt.lock."""
        world = snapshot.take(rt.world)
        try:
            result = action(self._director(rt, world))
            outcome = await result if inspect.isawaitable(result) else result
        except DirectorError as exc:
            raise BadRequest(str(exc)) from exc
        async with self.sessions.begin() as s:
            await self._stage(s, rt, outcome, world)
        rt.world = world
        rt.public_turns.extend(outcome["public_turns"])
        rt.tickers.extend(_tickers(outcome["private_turns"]))
        rt.snapshot_turns.append(world["game"]["turn"])
        return outcome

    # ------------------------------------------------------------------ broadcasts and Watson

    async def _broadcast_world(self, rt: GameRuntime, outcome: dict) -> None:
        gid = rt.game_id
        await self.hub.send(gid, "clock", {"clock": outcome["clock"]})
        for ev in outcome["world_events"]:
            await self.hub.send(gid, "world_event", {"text": ev.get("text", ""), "evidence": ev.get("evidence")})
        ticker = (outcome.get("offscreen") or {}).get("ticker")
        if ticker:
            await self.hub.send(gid, "ticker", {"text": ticker})
        if self.settings.debug_panel:
            for ev in outcome["guard_events"]:
                await self.hub.send(gid, "guard_event", ev)

    def _watson_input(self, rt: GameRuntime) -> dict:
        """Player-visible state only: public turns, public cast/evidence/locations, the public timeline."""
        case, world = rt.case, rt.world
        return {
            "turn": world["game"]["turn"],
            "turns": [{k: t[k] for k in _WATSON_TURN_KEYS if k in t} for t in rt.public_turns],
            "cast": [{"id": c["id"], "name": c["name"], "role": c["role"]} for c in public_cast(case, world)],
            "evidence": world_mod.public_evidence(case, world),
            "locations": public_locations(case, world),
            "timeline_public": case.get("timeline_public", []),
        }

    def _schedule_notebook(self, rt: GameRuntime, kind: str, background: BackgroundTasks) -> None:
        """PLAN §7.5: after every 2nd player turn and after every confrontation, once the response has gone out."""
        if kind == "confront" or rt.world["game"]["turn"] % 2 == 0:
            background.add_task(self._update_notebook, rt.game_id, rt.branch, self._watson_input(rt))

    async def _update_notebook(self, game_id: str, branch: int, visible: dict) -> None:
        entry = await watson.update(visible, self.llm_mode())
        rt = await self.runtime(game_id)
        async with rt.lock:
            if rt.branch != branch:
                return
            async with self.sessions.begin() as s:
                s.add(NotebookEntryRow(game_id=game_id, turn=entry["turn"], data=entry))
            if rt.notebook is None or entry["turn"] >= rt.notebook["turn"]:
                rt.notebook = entry
                await self.hub.send(game_id, "notebook_updated", entry)

    # ------------------------------------------------------------------ views

    def game_state(self, rt: GameRuntime) -> dict:
        case, world = rt.case, rt.world
        game = world["game"]
        return {
            "game_id": rt.game_id, "status": game["status"], "turn": game["turn"],
            "clock": world_mod.clock_str(game["clock_minutes"]), "case": _game_case(case),
            "difficulty": rt.difficulty, "llm_mode": self.llm_mode(), "cast": public_cast(case, world),
            "evidence": world_mod.public_evidence(case, world), "locations": public_locations(case, world),
            "turns": rt.public_turns, "notebook": rt.notebook, "ticker": rt.tickers[-TICKER_KEEP:],
            "accessibility": rt.accessibility, "can_rewind_to": [0, *rt.snapshot_turns],
        }

    def briefing(self, rt: GameRuntime) -> dict:
        case = _game_case(rt.case)
        return {"game_id": rt.game_id, "title": case["title"], "setting": case["setting"],
                "briefing": case["briefing"], "victim": case["victim"], "timeline_public": case["timeline_public"],
                "cast": public_cast(rt.case, rt.world), "evidence": world_mod.public_evidence(rt.case, rt.world),
                "locations": public_locations(rt.case, rt.world)}

    async def get_game(self, game_id: str) -> dict:
        return self.game_state(await self.runtime(game_id))

    async def list_games(self) -> list[dict]:
        async with self.sessions() as s:
            games = (await s.execute(
                select(GameRow, CaseRow.title, CaseRow.setting).join(CaseRow, CaseRow.id == GameRow.case_id)
                .order_by(GameRow.created_at.desc()))).all()
            accusations = {a.game_id: a for a in await s.scalars(
                select(AccusationRow).where(AccusationRow.archived.is_(False)))}
        out = []
        for g, title, setting in games:
            acc = accusations.get(g.id)
            out.append({"game_id": g.id, "case_id": g.case_id, "case_title": title, "setting": setting,
                        "difficulty": g.difficulty, "status": g.status, "turn": g.turn,
                        "created_at": g.created_at.isoformat(), "correct": acc.correct if acc else None,
                        "rank": acc.rank if acc else None})
        return out

    async def debug_state(self, game_id: str) -> dict:
        rt = await self.runtime(game_id)
        case, world = rt.case, rt.world
        async with self.sessions() as s:
            guard_events = await self._guard_rows(s, game_id)
            world_events = list((await s.scalars(
                select(TurnRow.output).where(TurnRow.game_id == game_id, TurnRow.type == "world",
                                             TurnRow.archived.is_(False)).order_by(TurnRow.turn, TurnRow.seq))).all())
        suspects = {}
        for s_ in case["suspects"]:
            st = world["suspects"][s_["id"]]
            unlocked, revealed = st["unlocked_secret_ids"], st["revealed_secret_ids"]
            suspects[s_["id"]] = {
                "name": s_["name"], "stress": st["stress"], "thresholds": s_["crack_thresholds"],
                "unlocked": unlocked, "locked": [x["id"] for x in s_["secrets"] if x["id"] not in unlocked],
                "revealed": revealed,
                "secrets": [{"id": x["id"], "tier": x["tier"], "text": x["text"],
                             "status": "revealed" if x["id"] in revealed else
                             "unlocked" if x["id"] in unlocked else "locked"} for x in s_["secrets"]],
                "heard_log": st["heard_log"], "outbox": st["outbox"], "emotion": st["emotion"],
                "last_honesty": st.get("last_honesty"), "last_internal_reasoning": st.get("last_internal_reasoning"),
                "last_accuses": st.get("last_accuses"), "system_blocks": st.get("last_system_blocks", []),
                "silenced_until": st.get("silenced_until"),
            }
        return {"llm_mode": self.llm_mode(), "models": self.models(), "turn": world["game"]["turn"],
                "clock": world_mod.clock_str(world["game"]["clock_minutes"]), "suspects": suspects,
                "evidence": {k: v["state"] for k, v in world["evidence"].items()}, "guard_events": guard_events,
                "world_events": world_events, "fired_framing_actions": world["game"]["fired_framing_actions"],
                "cross_contamination": cross_contamination(case, world)}

    # ------------------------------------------------------------------ actions

    async def create_game(self, case_id: str, difficulty: str, accessibility: dict) -> dict:
        case = await self.get_case(case_id)
        world = world_mod.initial_world(case, difficulty)
        fallback = await judge.fallback_lines(case, self.llm_mode())
        gid = uuid.uuid4().hex[:12]
        async with self.sessions.begin() as s:
            s.add(GameRow(id=gid, case_id=case_id, difficulty=difficulty, accessibility=accessibility,
                          status=world["game"]["status"], turn=0, clock_minutes=world["game"]["clock_minutes"],
                          fallback_lines=fallback))
            await s.flush()
            await self._write_projection(s, gid, world)
        rt = GameRuntime(game_id=gid, case_id=case_id, case=case, difficulty=difficulty, accessibility=accessibility,
                         fallback_lines=fallback, world=world, public_turns=[], tickers=[], snapshot_turns=[],
                         notebook=None)
        self._runtimes[gid] = rt
        return {"game_id": gid, "briefing": self.briefing(rt)}

    async def retry(self, game_id: str) -> dict:
        rt = await self.runtime(game_id)
        created = await self.create_game(rt.case_id, rt.difficulty, rt.accessibility)
        return {"game_id": created["game_id"]}

    async def turn(self, game_id: str, req: dict, background: BackgroundTasks) -> dict:
        rt = await self.runtime(game_id)
        async with rt.lock:
            outcome = await self._run(rt, lambda d: d.player_turn(req))
            reply = outcome["public_turns"][0]
            await self.hub.send(game_id, "turn_result", reply)
            await self._broadcast_world(rt, outcome)
            self._schedule_notebook(rt, req["type"], background)
        return reply

    async def confront(self, game_id: str, req: dict, background: BackgroundTasks) -> dict:
        rt = await self.runtime(game_id)

        async def on_line(line: dict) -> None:
            await self.hub.send(game_id, "confront_line", line)

        def take_interject() -> str | None:
            text, rt.interject = rt.interject, None
            return text

        async with rt.lock:
            rt.interject = (req.get("interject") or "").strip() or None
            outcome = await self._run(rt, lambda d: d.confront(req, on_line=on_line, get_interject=take_interject))
            await self.hub.send(game_id, "confront_done", {"turn": rt.world["game"]["turn"]})
            await self._broadcast_world(rt, outcome)
            self._schedule_notebook(rt, "confront", background)
        return {"lines": outcome["public_turns"]}

    async def interject(self, game_id: str, text: str) -> dict:
        rt = await self.runtime(game_id)
        rt.interject = text.strip() or None
        return {"ok": True, "queued": rt.interject is not None}

    async def search(self, game_id: str, location_id: str, background: BackgroundTasks) -> dict:
        rt = await self.runtime(game_id)
        async with rt.lock:
            outcome = await self._run(rt, lambda d: d.search(location_id))
            await self.hub.send(game_id, "turn_result", outcome["public_turns"][0])
            await self._broadcast_world(rt, outcome)
            self._schedule_notebook(rt, "search", background)
        return {"evidence": outcome["search"]["evidence"], "clock": outcome["clock"]}

    async def accuse(self, game_id: str, req: dict) -> dict:
        rt = await self.runtime(game_id)
        async with rt.lock:
            motive = await judge.grade_motive(req.get("motive_text") or "",
                                              (rt.case.get("solution") or {}).get("motive", ""), self.llm_mode())

            async def act(d: Director) -> dict:
                outcome = await d.accuse(req, motive["points"])
                outcome["accusation"]["motive_note"] = motive["note"]
                return outcome

            await self._run(rt, act)
        return await self.debrief(game_id)

    async def debrief(self, game_id: str) -> dict:
        rt = await self.runtime(game_id)
        if rt.world["game"]["status"] != "closed":
            raise NotFound("the debrief opens once the case is closed")
        async with self.sessions() as s:
            data = await s.scalar(
                select(AccusationRow.debrief)
                .where(AccusationRow.game_id == game_id, AccusationRow.archived.is_(False))
                .order_by(AccusationRow.created_at.desc()).limit(1))
        if data is None:
            raise NotFound("no accusation on record")
        return data

    async def rewind(self, game_id: str, turn: int) -> dict:
        """PLAN §8.10: restore the snapshot taken after ``turn`` (0 = the briefing) and archive everything later."""
        rt = await self.runtime(game_id)
        async with rt.lock:
            if turn != 0 and turn not in rt.snapshot_turns:
                raise BadRequest(f"no snapshot for turn {turn}; choose one of {[0, *rt.snapshot_turns]}")
            async with self.sessions.begin() as s:
                for model in (TurnRow, GuardrailEventRow, NotebookEntryRow, AccusationRow):
                    await s.execute(update(model)
                                    .where(model.game_id == game_id, model.turn > turn, model.archived.is_(False))
                                    .values(archived=True))
                fresh = await self._read_runtime(s, game_id)
                await self._write_projection(s, game_id, fresh.world)
            rt.rewind_to(fresh)
            return self.game_state(rt)
