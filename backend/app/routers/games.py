"""Game routes (PLAN §9, docs/INTERFACES.md §6). Every action persists its turn and snapshot before it returns."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks

from ..schemas import (
    AccuseRequest,
    ConfrontRequest,
    ConfrontResponse,
    CreateGameRequest,
    CreateGameResponse,
    GameState,
    GameSummary,
    InterjectRequest,
    InterjectResponse,
    PublicTurn,
    RetryResponse,
    RewindRequest,
    SearchRequest,
    SearchResponse,
    TurnRequest,
)
from .deps import Service

router = APIRouter(prefix="/games", tags=["games"])

# A key the engine omitted stays omitted, and an explicit null stays null.
_PUBLIC = {"response_model_exclude_unset": True}


@router.get("", response_model=list[GameSummary])
async def list_games(svc: Service) -> list[dict]:
    return await svc.list_games()


@router.post("", status_code=201, response_model=CreateGameResponse, **_PUBLIC)
async def create_game(body: CreateGameRequest, svc: Service) -> dict:
    return await svc.create_game(body.case_id, body.difficulty, body.accessibility)


@router.get("/{game_id}", response_model=GameState, **_PUBLIC)
async def get_game(game_id: str, svc: Service) -> dict:
    return await svc.get_game(game_id)


@router.post("/{game_id}/turn", response_model=PublicTurn, **_PUBLIC)
async def turn(game_id: str, body: TurnRequest, background: BackgroundTasks, svc: Service) -> dict:
    return await svc.turn(game_id, body.model_dump(), background)


@router.post("/{game_id}/confront", response_model=ConfrontResponse, **_PUBLIC)
async def confront(game_id: str, body: ConfrontRequest, background: BackgroundTasks, svc: Service) -> dict:
    return await svc.confront(game_id, body.model_dump(), background)


@router.post("/{game_id}/confront/interject", response_model=InterjectResponse)
async def interject(game_id: str, body: InterjectRequest, svc: Service) -> dict:
    return await svc.interject(game_id, body.text)


@router.post("/{game_id}/search", response_model=SearchResponse, **_PUBLIC)
async def search(game_id: str, body: SearchRequest, background: BackgroundTasks, svc: Service) -> dict:
    return await svc.search(game_id, body.location_id, background, body.evidence_id)


@router.post("/{game_id}/accuse")
async def accuse(game_id: str, body: AccuseRequest, svc: Service) -> dict[str, Any]:
    """The Debrief: the one public response allowed to carry private reasoning, and only once the case is closed."""
    return await svc.accuse(game_id, body.model_dump())


@router.get("/{game_id}/debrief")
async def debrief(game_id: str, svc: Service) -> dict[str, Any]:
    return await svc.debrief(game_id)


@router.post("/{game_id}/rewind", response_model=GameState, **_PUBLIC)
async def rewind(game_id: str, body: RewindRequest, svc: Service) -> dict:
    return await svc.rewind(game_id, body.turn)


@router.post("/{game_id}/retry", response_model=RetryResponse)
async def retry(game_id: str, svc: Service) -> dict:
    return await svc.retry(game_id)
