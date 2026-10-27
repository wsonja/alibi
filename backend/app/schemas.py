"""Request and response models (PLAN §9, docs/INTERFACES.md §6; mirrored by frontend/src/api/types.ts).

Public response models whitelist keys: FastAPI drops any key a model does not declare, so a private field added to an
engine dict cannot reach the browser through these shapes. Routes serialize with ``response_model_exclude_unset`` so a
key the engine omitted stays omitted and an explicit null stays null. Debrief and DebugState stay loose dicts: they are
the two places private state is allowed out.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["rookie", "detective", "inspector"]


# --------------------------------------------------------------------------------------------- requests

class _Request(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ApiKeyRequest(_Request):
    api_key: str = Field(min_length=1)


class ImportCaseRequest(_Request):
    case: dict[str, Any]


class GenerateCaseRequest(_Request):
    setting: str = ""
    n_suspects: int = 4
    difficulty: Difficulty = "detective"


class CreateGameRequest(_Request):
    case_id: str
    difficulty: Difficulty = "detective"
    accessibility: dict[str, Any] = Field(default_factory=dict)


class TurnRequest(_Request):
    type: Literal["ask", "tactic", "present"]
    suspect_id: str
    text: str | None = None
    tactic: str | None = None
    evidence_id: str | None = None
    player_signal: dict[str, Any] | None = None


class ConfrontRequest(_Request):
    a: str
    b: str
    topic: str
    rounds: int | None = None
    interject: str | None = None
    player_signal: dict[str, Any] | None = None


class InterjectRequest(_Request):
    text: str = ""


class SearchRequest(_Request):
    location_id: str


class AccuseRequest(_Request):
    suspect_id: str
    method_evidence_ids: list[str] = Field(default_factory=list)
    motive_text: str = ""
    confidence: float = 0.5


class RewindRequest(_Request):
    turn: int = Field(ge=0)


# --------------------------------------------------------------------------------------------- public responses

class ModelLadder(BaseModel):
    suspect: str
    author: str
    guard: str


class Health(BaseModel):
    ok: bool
    llm_mode: str
    debug_panel: bool
    models: ModelLadder
    cases: int


class ApiKeyResponse(BaseModel):
    llm_mode: str


class CaseSummary(BaseModel):
    id: str
    title: str
    setting: str
    generated: bool
    n_suspects: int
    preset: str


class ImportCaseResponse(BaseModel):
    case_id: str


class SuspectVoice(BaseModel):
    webspeech_index: int | None = None
    base_pitch: float | None = None


class PublicSuspect(BaseModel):
    id: str
    name: str
    role: str
    public_description: str
    portrait_prompt: str
    portrait_url: str | None
    stress_pct: int
    emotion: str
    tell: str
    silenced: bool
    last_seen_location: str
    voice: SuspectVoice | None


class PublicEvidence(BaseModel):
    id: str
    name: str
    location: str | None
    state: str
    description: str
    examined_detail: str | None = None


class PublicLocation(BaseModel):
    id: str
    name: str
    description: str
    searched: bool


class PublicTurn(BaseModel):
    turn: int
    seq: int
    type: str
    actor: str
    target: str | None
    clock: str
    detective_text: str | None = None
    tactic: str | None = None
    evidence_id: str | None = None
    spoken: str | None = None
    tell: str | None = None
    emotion: str | None = None
    stress_pct: int | None = None
    other: str | None = None


class TimelineEntry(BaseModel):
    time: str
    event: str


class PublicVictim(BaseModel):
    name: str
    description: str
    cause_of_death_public: str


class GameCase(BaseModel):
    id: str
    title: str
    setting: str
    briefing: str
    victim: PublicVictim
    timeline_public: list[TimelineEntry]


class NotebookClaim(BaseModel):
    quote: str
    where: str
    from_: str = Field(alias="from", serialization_alias="from")
    to: str

    model_config = ConfigDict(populate_by_name=True)


class NotebookSuspect(BaseModel):
    id: str
    claims: list[NotebookClaim]
    notes: list[str]


class ContradictionA(BaseModel):
    suspect: str
    quote: str


class ContradictionB(BaseModel):
    suspect_or_evidence: str
    quote: str


class NotebookContradiction(BaseModel):
    a: ContradictionA
    b: ContradictionB
    note: str


class NotebookEntry(BaseModel):
    turn: int
    per_suspect: list[NotebookSuspect]
    contradictions: list[NotebookContradiction]
    suggested_next: list[str]


class Briefing(BaseModel):
    game_id: str
    title: str
    setting: str
    briefing: str
    victim: PublicVictim
    timeline_public: list[TimelineEntry]
    cast: list[PublicSuspect]
    evidence: list[PublicEvidence]
    locations: list[PublicLocation]


class CreateGameResponse(BaseModel):
    game_id: str
    briefing: Briefing


class GameState(BaseModel):
    game_id: str
    status: str
    turn: int
    clock: str
    case: GameCase
    difficulty: str
    llm_mode: str
    cast: list[PublicSuspect]
    evidence: list[PublicEvidence]
    locations: list[PublicLocation]
    turns: list[PublicTurn]
    notebook: NotebookEntry | None
    ticker: list[str]
    accessibility: dict[str, Any]
    can_rewind_to: list[int]


class GameSummary(BaseModel):
    game_id: str
    case_id: str
    case_title: str
    setting: str
    difficulty: str
    status: str
    turn: int
    created_at: str
    correct: bool | None
    rank: str | None


class ConfrontResponse(BaseModel):
    lines: list[PublicTurn]


class InterjectResponse(BaseModel):
    ok: bool
    queued: bool


class SearchResponse(BaseModel):
    evidence: list[PublicEvidence]
    clock: str


class RetryResponse(BaseModel):
    game_id: str
