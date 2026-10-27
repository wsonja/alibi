from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["tts"])


@router.post("/tts")
async def tts() -> None:
    raise HTTPException(501, "Server voices (ElevenLabs, PLAN M5) are not built yet. The browser voice is used instead.")
