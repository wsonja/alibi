"""ORM tables (PLAN §5). JSON columns work on SQLite and Postgres.

Restore reads ``turns.snapshot`` (the last non-archived one, else the case's initial world). ``suspect_state`` and
``evidence_state`` are a queryable projection of that snapshot, rewritten in the same transaction as each turn.
Rewind archives later rows in every turn-scoped table instead of deleting them.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class _Row:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseRow(_Row, Base):
    __tablename__ = "cases"
    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    setting: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    generated: Mapped[bool] = mapped_column(Boolean, default=False)
    checker_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class GameRow(_Row, Base):
    __tablename__ = "games"
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    difficulty: Mapped[str] = mapped_column(String(20))
    accessibility: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="briefing")
    turn: Mapped[int] = mapped_column(Integer, default=0)
    clock_minutes: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fallback_lines: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SuspectStateRow(_Row, Base):
    __tablename__ = "suspect_state"
    __table_args__ = (UniqueConstraint("game_id", "suspect_id"),)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    suspect_id: Mapped[str] = mapped_column(String(100))
    stress: Mapped[int] = mapped_column(Integer, default=0)
    unlocked_secret_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    revealed_secret_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    heard_log: Mapped[list[Any]] = mapped_column(JSON, default=list)
    outbox: Mapped[list[Any]] = mapped_column(JSON, default=list)
    flatter_count: Mapped[int] = mapped_column(Integer, default=0)
    threaten_count: Mapped[int] = mapped_column(Integer, default=0)
    silenced_until: Mapped[int | None] = mapped_column(Integer, nullable=True)
    emotion: Mapped[str] = mapped_column(String(20), default="neutral")
    last_seen_location: Mapped[str] = mapped_column(String(100), default="")
    conversation: Mapped[list[Any]] = mapped_column(JSON, default=list)


class EvidenceStateRow(_Row, Base):
    __tablename__ = "evidence_state"
    __table_args__ = (UniqueConstraint("game_id", "evidence_id"),)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(20))
    examined_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TurnRow(_Row, Base):
    """One Director row. ``public`` is the PublicTurn the player saw for this (turn, seq), if any; ``snapshot`` is the
    full world after the action and sits on the action's last row."""
    __tablename__ = "turns"
    __table_args__ = (Index("ix_turns_game_order", "game_id", "turn", "seq"),)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    turn: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(100))
    target: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input: Mapped[Any] = mapped_column(JSON, nullable=True)
    output: Mapped[Any] = mapped_column(JSON, nullable=True)
    public: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    stress_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class GuardrailEventRow(_Row, Base):
    __tablename__ = "guardrail_events"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    turn: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suspect_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[Any] = mapped_column(JSON, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class NotebookEntryRow(_Row, Base):
    __tablename__ = "notebook_entries"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    turn: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class AccusationRow(_Row, Base):
    __tablename__ = "accusations"
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    turn: Mapped[int] = mapped_column(Integer)
    suspect_id: Mapped[str] = mapped_column(String(100))
    method_evidence_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    motive_text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float)
    score: Mapped[dict[str, Any]] = mapped_column(JSON)
    correct: Mapped[bool] = mapped_column(Boolean)
    rank: Mapped[str] = mapped_column(String(20))
    debrief: Mapped[dict[str, Any]] = mapped_column(JSON)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
