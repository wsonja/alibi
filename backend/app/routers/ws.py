from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..engine.world import clock_str
from ..services.game_service import GameService, NotFound

router = APIRouter(tags=["ws"])


@router.websocket("/ws/games/{game_id}")
async def game_socket(ws: WebSocket, game_id: str) -> None:
    """Server-push only. Events arrive as ``{type, data}``; anything the client sends is ignored. A (re)connecting
    client first gets the current clock, sent after registration so no later event can be missed."""
    svc: GameService = ws.app.state.service
    await ws.accept()
    try:
        rt = await svc.runtime(game_id)
    except NotFound:
        await ws.close(code=4404, reason="unknown game")
        return
    svc.hub.add(game_id, ws)
    try:
        await ws.send_json({"type": "clock", "data": {"clock": clock_str(rt.world["game"]["clock_minutes"])}})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        svc.hub.remove(game_id, ws)
