"""Process settings read from backend/.env (docs/INTERFACES.md §4).

The agents package reads its LLM configuration from ``os.environ`` (it must not import the app layer), so
``export_llm_env`` copies the LLM-related values there once at startup.
"""
from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
DOTENV_PATH = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=DOTENV_PATH, env_ignore_empty=True, extra="ignore")

    gemini_api_key: str = ""
    suspect_model: str = ""
    author_model: str = ""
    guard_model: str = ""
    database_url: str = "sqlite+aiosqlite:///./alibi.db"
    debug_panel: bool = False
    offscreen_every: int = 3
    llm_mode: str = "auto"
    fake_llm: bool = False
    rng_seed: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    dotenv_path: Path = DOTENV_PATH

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Relative SQLite paths resolve against backend/, so the DB is backend/alibi.db wherever uvicorn starts."""
        prefix = "sqlite+aiosqlite:///"
        url = self.database_url
        if url.startswith(prefix) and not url.startswith(prefix + "/") and ":memory:" not in url:
            return prefix + str((BACKEND_DIR / url[len(prefix):]).resolve())
        return url


_LLM_ENV = {
    "GEMINI_API_KEY": "gemini_api_key",
    "SUSPECT_MODEL": "suspect_model",
    "AUTHOR_MODEL": "author_model",
    "GUARD_MODEL": "guard_model",
}


def export_llm_env(settings: Settings) -> None:
    for env_name, attr in _LLM_ENV.items():
        value = getattr(settings, attr)
        if value:
            os.environ.setdefault(env_name, value)


def write_dotenv_value(path: Path, name: str, value: str) -> None:
    """Set ``name=value`` in a .env file, keeping every other line. Atomic, so a crash never leaves half a file."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    entry = f"{name}={value}"
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == name:
            lines[i] = entry
            break
    else:
        lines.append(entry)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".env.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


@lru_cache
def get_settings() -> Settings:
    return Settings()
