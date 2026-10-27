from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..schemas import CaseSummary, GenerateCaseRequest, ImportCaseRequest, ImportCaseResponse
from ..services.game_service import NotFound
from .deps import Service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseSummary])
async def list_cases(svc: Service) -> list[dict]:
    return await svc.list_cases()


@router.post("/import", response_model=ImportCaseResponse)
async def import_case(body: ImportCaseRequest, svc: Service) -> dict:
    return {"case_id": await svc.import_case(body.case)}


@router.post("/generate", status_code=202)
async def generate_case(body: GenerateCaseRequest, svc: Service) -> dict:
    if svc.llm_mode() != "gemini":
        raise HTTPException(503, "Generating a case needs Gemini. Add a GEMINI_API_KEY in Settings, then try again.")
    raise HTTPException(501, "Case generation (the Author, PLAN M6) is not built yet. Play a shipped case or import one.")


@router.get("/jobs/{job_id}")
async def case_job(job_id: str) -> dict:
    raise NotFound(f"unknown job {job_id!r}")


@router.get("/{case_id}/export")
async def export_case(case_id: str, svc: Service) -> dict[str, Any]:
    """The full case (a share seed), solution and secrets included, so it sits behind the same gate as /debug:
    PLAN §2.7 lets secrets leave the server only when DEBUG_PANEL=1."""
    if not svc.settings.debug_panel:
        raise NotFound("case export is available only with DEBUG_PANEL=1")
    return await svc.get_case(case_id)
