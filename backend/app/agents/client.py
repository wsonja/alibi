"""Gemini client for every LLM call in the game (docs/INTERFACES.md §0.2-0.4).

This module is the only place that talks to ``google.genai``.  It knows nothing about suspects or cases: callers hand
it a system text, a list of ``{"role", "content"}`` messages and a *tool* (``{"name", "description", "input_schema"}``
from ``tools.py``) and get back the parsed JSON object the model produced under that schema.

Policy (INTERFACES §0.3):
  * model ladder = the configured comma-separated list for the role, then ``gemini-3.5-flash-lite``,
    ``gemini-3.1-flash-lite`` (deduplicated, order preserved);
  * 429 / 503 / other 5xx / timeouts / connection errors -> sleep 1.5 s, retry the same model once, then move down;
  * 400 INVALID_ARGUMENT while ``thinking_config`` is set -> retry the same model once without it;
  * 404 (unknown model) -> next model immediately;
  * unparsable JSON or missing required keys -> retry once with "Return only the JSON object." appended, then
    ``InvalidOutput``;
  * every model exhausted -> ``LLMUnavailable``.

The API key is never logged.  Model, latency and token usage are.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("alibi.agents.client")

# --------------------------------------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------------------------------------


class LLMError(Exception):
    """Base class for everything this module raises on purpose."""


class InvalidOutput(LLMError):
    """The model answered, but not with a JSON object that satisfies the tool schema."""


class LLMUnavailable(LLMError):
    """Every model in the ladder failed (quota, outage, network, unknown model...)."""


class NotConfigured(LLMError):
    """A Gemini-only feature was requested but no credential is available."""


# --------------------------------------------------------------------------------------------------------------------
# Settings helper (agents must not import app.config: the app lane owns it and sets env vars before importing us)
# --------------------------------------------------------------------------------------------------------------------

DEFAULT_MODELS = {
    "suspect": "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.6-flash",
    "author": "gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite",
    "guard": "gemini-3.5-flash-lite,gemini-3.1-flash-lite",
}
LADDER_TAIL = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
ROLE_ENV = {"suspect": "SUSPECT_MODEL", "author": "AUTHOR_MODEL", "guard": "GUARD_MODEL"}

RETRY_SLEEP_S = 1.5
REQUEST_TIMEOUT_S = 90.0

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"
_dotenv_loaded = False


def _load_dotenv_once() -> None:
    """Load backend/.env into os.environ (without overriding existing variables) at most once."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    if not _ENV_FILE.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_ENV_FILE, override=False)
    except Exception as exc:  # noqa: BLE001 - dotenv is installed; be defensive anyway
        log.debug("could not load %s: %s", _ENV_FILE, exc)


def api_key() -> str | None:
    """The Gemini key from GEMINI_API_KEY or GOOGLE_API_KEY (loading backend/.env if neither is set). Never log it."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        _load_dotenv_once()
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    key = (key or "").strip()
    return key or None


def credential_available() -> bool:
    """True iff a non-empty Gemini key is present."""
    return api_key() is not None


def configured_models(role: str) -> str:
    """The comma-separated model ladder configured for ``role`` (suspect|author|guard)."""
    env_name = ROLE_ENV.get(role)
    if env_name is None:
        # a literal model name / ladder was passed instead of a role
        return role
    value = os.environ.get(env_name, "").strip()
    if not value:
        _load_dotenv_once()
        value = os.environ.get(env_name, "").strip()
    return value or DEFAULT_MODELS[role]


def model_ladder(model: str) -> list[str]:
    """Expand a role name or comma-separated model list into the ordered, de-duplicated ladder."""
    names = [m.strip() for m in configured_models(model).split(",")]
    ladder: list[str] = []
    for name in names + LADDER_TAIL:
        if name and name not in ladder:
            ladder.append(name)
    return ladder


def models_summary() -> dict[str, str]:
    """{suspect, author, guard} -> preferred model name (for /health and the Judge Panel)."""
    return {role: model_ladder(role)[0] for role in ("suspect", "author", "guard")}


def resolve_mode(settings: Any = None) -> str:
    """Honour LLM_MODE=auto|gemini|scripted and FAKE_LLM=1 (an alias for scripted).

    ``settings`` may be None (read os.environ), a dict, or an object with ``llm_mode`` / ``fake_llm`` attributes.
    ``auto`` resolves to ``gemini`` iff a credential is available.
    """
    mode: Any = None
    fake: Any = None
    if settings is None:
        mode = os.environ.get("LLM_MODE")
        fake = os.environ.get("FAKE_LLM")
    elif isinstance(settings, dict):
        mode = settings.get("llm_mode", settings.get("LLM_MODE"))
        fake = settings.get("fake_llm", settings.get("FAKE_LLM"))
    else:
        mode = getattr(settings, "llm_mode", None) or getattr(settings, "LLM_MODE", None)
        fake = getattr(settings, "fake_llm", None)
        if fake is None:
            fake = getattr(settings, "FAKE_LLM", None)
    if str(fake).strip().lower() in {"1", "true", "yes", "on"}:
        return "scripted"
    mode = (str(mode).strip().lower() if mode is not None else "") or "auto"
    if mode == "scripted":
        return "scripted"
    if mode == "gemini":
        return "gemini"
    if mode != "auto":
        log.warning("unknown LLM_MODE=%r; treating as auto", mode)
    return "gemini" if credential_available() else "scripted"


# --------------------------------------------------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------------------------------------------------

_client: Any = None
_client_key: str | None = None


def get_client() -> Any:
    """Lazily construct the shared ``genai.Client``. Raises NotConfigured without a key."""
    global _client, _client_key
    key = api_key()
    if not key:
        raise NotConfigured("No Gemini credential: set GEMINI_API_KEY (or GOOGLE_API_KEY) in backend/.env")
    if _client is None or _client_key != key:
        from google import genai

        _client = genai.Client(api_key=key)
        _client_key = key
    return _client


def reset_client() -> None:
    """Forget the cached client (used after the key changes at runtime and by tests)."""
    global _client, _client_key
    _client = None
    _client_key = None


# --------------------------------------------------------------------------------------------------------------------
# Message conversion
# --------------------------------------------------------------------------------------------------------------------

_ROLE_MAP = {"user": "user", "assistant": "model", "model": "model", "system": "user", "detective": "user"}


def normalise_messages(messages: list[dict]) -> list[dict]:
    """Return ``[{"role": "user"|"model", "content": str}, ...]`` obeying Gemini's rules.

    Gemini requires the first content to be a user turn and strict alternation, so consecutive same-role messages are
    merged (joined with a blank line), a leading model turn gets a neutral user turn in front of it, and empty
    messages are dropped.
    """
    out: list[dict] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = _ROLE_MAP.get(str(m.get("role", "user")).lower(), "user")
        content = m.get("content")
        if content is None:
            content = m.get("text", "")
        content = str(content).strip()
        if not content:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"] = out[-1]["content"] + "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    if out and out[0]["role"] == "model":
        out.insert(0, {"role": "user", "content": "(The detective enters the room.)"})
    if not out:
        out.append({"role": "user", "content": "(The detective waits.)"})
    if out[-1]["role"] == "model":
        out.append({"role": "user", "content": "(The detective waits for you to go on.)"})
    return out


def _to_contents(messages: list[dict]) -> list[Any]:
    from google.genai import types

    return [
        types.Content(role=m["role"], parts=[types.Part(text=m["content"])]) for m in normalise_messages(messages)
    ]


# --------------------------------------------------------------------------------------------------------------------
# Output parsing
# --------------------------------------------------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_json_object(text: str | None) -> dict:
    """Parse the model text into a JSON object, tolerating code fences and leading/trailing prose."""
    if text is None:
        raise InvalidOutput("empty response")
    raw = text.strip()
    if not raw:
        raise InvalidOutput("empty response")
    m = _FENCE_RE.match(raw)
    if m:
        raw = m.group(1)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise InvalidOutput(f"not JSON: {raw[:120]!r}") from None
        try:
            obj = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise InvalidOutput(f"not JSON: {exc}") from None
    if isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], dict):
        obj = obj[0]
    if not isinstance(obj, dict):
        raise InvalidOutput(f"expected a JSON object, got {type(obj).__name__}")
    return obj


def validate_required(obj: dict, tool: dict) -> None:
    schema = tool.get("input_schema") or {}
    missing = [k for k in schema.get("required", []) if k not in obj]
    if missing:
        raise InvalidOutput(f"{tool.get('name')}: missing required keys {missing}")


def _status_of(exc: Exception) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    return None


def _usage_dict(response: Any) -> dict:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", None),
        "output_tokens": getattr(usage, "candidates_token_count", None),
        "thoughts_tokens": getattr(usage, "thoughts_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
    }


def _response_text(response: Any) -> str | None:
    try:
        text = response.text
    except Exception as exc:  # noqa: BLE001 - the SDK raises assorted errors for blocked/empty candidates
        log.debug("response.text unavailable: %s", exc)
        text = None
    if text:
        return text
    # Fall back to concatenating text parts (e.g. when a part is flagged as a thought).
    try:
        for cand in response.candidates or []:
            parts = getattr(getattr(cand, "content", None), "parts", None) or []
            chunks = [p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)]
            if chunks:
                return "".join(chunks)
    except Exception as exc:  # noqa: BLE001 - malformed candidates are treated as an empty answer
        log.debug("could not read candidate parts: %s", exc)
    return None


# --------------------------------------------------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------------------------------------------------

_last_call_info: dict = {}


def last_call_info() -> dict:
    """Model / latency / usage of the most recent successful call (for scripts and tests)."""
    return dict(_last_call_info)


async def call_tool(
    model: str,
    system_text: str,
    messages: list[dict],
    tool: dict,
    *,
    max_tokens: int = 1200,
    temperature: float = 0.9,
) -> dict:
    """Run one structured-output Gemini call and return the parsed JSON object.

    ``model`` is a role (``suspect``|``author``|``guard``) or a comma-separated list of model names.
    ``messages`` are ``{"role": "user"|"assistant", "content": str}`` dicts (assistant -> Gemini "model").
    ``tool`` is one of the schemas in ``tools.py``; its ``input_schema`` becomes ``response_json_schema``.
    """
    from google.genai import errors, types

    client = get_client()  # raises NotConfigured
    schema = tool["input_schema"]
    ladder = model_ladder(model)
    contents = _to_contents(messages)
    thinking_supported = True
    last_error: Exception | None = None

    async def _once(model_name: str, contents_: list[Any], with_thinking: bool) -> Any:
        cfg: dict[str, Any] = {
            "system_instruction": system_text,
            "response_mime_type": "application/json",
            "response_json_schema": schema,
            "max_output_tokens": max_tokens,
            "temperature": temperature,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
            "http_options": types.HttpOptions(timeout=int(REQUEST_TIMEOUT_S * 1000)),
        }
        if with_thinking:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_level="low")
        return await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model_name, contents=contents_, config=types.GenerateContentConfig(**cfg)
            ),
            timeout=REQUEST_TIMEOUT_S + 5,
        )

    for model_name in ladder:
        attempts_left = 2  # one retry on transient failure per model
        with_thinking = thinking_supported
        invalid_retry_done = False
        current_contents = contents
        while attempts_left > 0:
            attempts_left -= 1
            started = time.perf_counter()
            try:
                response = await _once(model_name, current_contents, with_thinking)
            except errors.APIError as exc:
                status = _status_of(exc)
                last_error = exc
                if status == 400 and with_thinking:
                    log.warning("%s rejected thinking_config (400); retrying without it", model_name)
                    with_thinking = False
                    thinking_supported = False
                    attempts_left += 1  # this retry does not consume the transient budget
                    continue
                if status == 404:
                    log.warning("%s: unknown model (404); moving down the ladder", model_name)
                    break
                if status in (429, 503) or (status is not None and status >= 500):
                    log.warning("%s: %s; %s", model_name, status, "retrying in 1.5 s" if attempts_left else "giving up")
                    if attempts_left:
                        await asyncio.sleep(RETRY_SLEEP_S)
                        continue
                    break
                log.warning("%s: client error %s: %s", model_name, status, str(exc)[:200])
                break
            except (TimeoutError, ConnectionError, OSError) as exc:
                last_error = exc
                log.warning("%s: %s; %s", model_name, type(exc).__name__, "retrying" if attempts_left else "giving up")
                if attempts_left:
                    await asyncio.sleep(RETRY_SLEEP_S)
                    continue
                break
            except Exception as exc:  # noqa: BLE001 - httpx errors etc. surface as their own types
                last_error = exc
                name = type(exc).__name__
                transient = any(k in name.lower() for k in ("timeout", "connect", "network", "remote", "protocol"))
                log.warning("%s: %s: %s", model_name, name, str(exc)[:200])
                if transient and attempts_left:
                    await asyncio.sleep(RETRY_SLEEP_S)
                    continue
                break

            latency_ms = int((time.perf_counter() - started) * 1000)
            usage = _usage_dict(response)
            log.info(
                "gemini call model=%s tool=%s latency_ms=%d prompt_tokens=%s output_tokens=%s thoughts_tokens=%s",
                model_name,
                tool.get("name"),
                latency_ms,
                usage.get("prompt_tokens"),
                usage.get("output_tokens"),
                usage.get("thoughts_tokens"),
            )
            try:
                obj = parse_json_object(_response_text(response))
                validate_required(obj, tool)
            except InvalidOutput as exc:
                log.warning("%s: invalid output for %s: %s", model_name, tool.get("name"), exc)
                if invalid_retry_done:
                    raise
                invalid_retry_done = True
                attempts_left += 1
                fixed = normalise_messages(messages)
                fixed[-1] = {
                    "role": "user",
                    "content": fixed[-1]["content"] + "\n\nReturn only the JSON object.",
                }
                current_contents = _to_contents(fixed)
                continue
            _last_call_info.clear()
            _last_call_info.update(
                {"model": model_name, "latency_ms": latency_ms, "tool": tool.get("name"), **usage}
            )
            return obj

    raise LLMUnavailable(f"all models failed for {tool.get('name')}: {ladder} (last error: {last_error})")
