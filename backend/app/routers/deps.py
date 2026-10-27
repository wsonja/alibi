from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from ..services.game_service import GameService


def get_service(request: Request) -> GameService:
    return request.app.state.service


Service = Annotated[GameService, Depends(get_service)]
