from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..services.game_service import NotFound
from .deps import Service

router = APIRouter(tags=["debug"])


@router.get("/games/{game_id}/debug")
async def debug_state(game_id: str, svc: Service) -> dict[str, Any]:
    """Full private state for the Judge Panel. PLAN §2.7: it exists only when DEBUG_PANEL=1."""
    if not svc.settings.debug_panel:
        raise NotFound("the debug panel is off (DEBUG_PANEL=0)")
    return await svc.debug_state(game_id)
