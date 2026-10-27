from __future__ import annotations

import os
import re

from fastapi import APIRouter

from ..agents.client import reset_client
from ..config import write_dotenv_value
from ..schemas import ApiKeyRequest, ApiKeyResponse
from ..services.game_service import BadRequest
from .deps import Service

router = APIRouter(prefix="/settings", tags=["settings"])

_KEY_SHAPE = re.compile(r"[A-Za-z0-9._\-]+")


@router.post("/api-key", response_model=ApiKeyResponse)
async def set_api_key(body: ApiKeyRequest, svc: Service) -> dict:
    """Local dev convenience: store a Gemini key in backend/.env and use it from the next call on. The key is never
    logged or echoed back."""
    key = body.api_key.strip()
    if not _KEY_SHAPE.fullmatch(key):
        raise BadRequest("That does not look like a Gemini API key (letters, digits, '-', '_' and '.' only).")
    write_dotenv_value(svc.settings.dotenv_path, "GEMINI_API_KEY", key)
    os.environ["GEMINI_API_KEY"] = key
    svc.settings.gemini_api_key = key
    reset_client()
    return {"llm_mode": svc.llm_mode()}
