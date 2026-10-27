"""FastAPI app (docs/INTERFACES.md §4). Run from backend/: ``.venv/bin/uvicorn app.main:app --port 8000``."""
from __future__ import annotations

import logging
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, export_llm_env, get_settings
from .db import create_all, make_engine, make_sessionmaker
from .routers import cases, debug, games, tts, ws
from .routers import settings as settings_router
from .routers.deps import Service
from .schemas import Health
from .services.game_service import BadRequest, GameService, Hub, NotFound

CASES_DIR = pathlib.Path(__file__).resolve().parent / "cases"
# The Vite dev server is also reached over the LAN (vite --host), from whatever address the host has.
LAN_DEV_ORIGIN = r"https?://[^/]+:5173"

log = logging.getLogger("alibi")


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        export_llm_env(settings)
        engine = make_engine(settings.resolved_database_url)
        await create_all(engine)
        service = GameService(settings, make_sessionmaker(engine), Hub())
        await service.sync_case_files(CASES_DIR)
        app.state.service = service
        log.info("alibi ready: llm_mode=%s debug_panel=%s cases=%d", service.llm_mode(), settings.debug_panel,
                 await service.case_count())
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Alibi", version="1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_origin_regex=LAN_DEV_ORIGIN,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound) -> JSONResponse:
        return _error(404, str(exc))

    @app.exception_handler(BadRequest)
    async def bad_request(_: Request, exc: BadRequest) -> JSONResponse:
        return _error(400, str(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, exc.detail if isinstance(exc.detail, str) else str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        # loc + msg only: echoing the input back could repeat a pasted API key.
        parts = [f"{'.'.join(str(p) for p in e['loc'][1:]) or 'body'}: {e['msg']}" for e in exc.errors()]
        return _error(422, "; ".join(parts) or "invalid request")

    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=Health)
    async def health(svc: Service) -> dict:
        return {"ok": True, "llm_mode": svc.llm_mode(), "debug_panel": settings.debug_panel, "models": svc.models(),
                "cases": await svc.case_count()}

    for module in (cases, games, debug, ws, settings_router, tts):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
