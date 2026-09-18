#!/usr/bin/env python
"""One tiny structured call per configured model (PLAN M0 / §17).

Prints OK (with latency) or the error for every model in the SUSPECT_MODEL / AUTHOR_MODEL / GUARD_MODEL ladders.
Exits 0 even when no credential is configured (it tells you how to add one).

    python scripts/ping_models.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PING_TOOL = {
    "name": "ping",
    "description": "Reply with ok=true.",
    "input_schema": {
        "type": "object",
        "required": ["ok", "word"],
        "properties": {"ok": {"type": "boolean"}, "word": {"type": "string", "description": "one English word"}},
    },
}


async def ping(model_name: str) -> tuple[bool, str]:
    from app.agents import client as llm

    started = time.perf_counter()
    try:
        out = await llm.call_tool(
            model_name,
            "You answer with a tiny JSON object.",
            [{"role": "user", "content": "Return ok=true and one word."}],
            PING_TOOL,
            max_tokens=200,
            temperature=0.0,
        )
        ms = int((time.perf_counter() - started) * 1000)
        info = llm.last_call_info()
        served = info.get("model")
        if served != model_name:
            return False, f"fell through to {served} after {ms} ms (the requested model failed)"
        return bool(out.get("ok")), f"{ms} ms, word={out.get('word')!r}, tokens={info.get('prompt_tokens')}/{info.get('output_tokens')}"
    except Exception as exc:  # noqa: BLE001 - we report every failure kind
        ms = int((time.perf_counter() - started) * 1000)
        return False, f"{type(exc).__name__}: {str(exc)[:160]} ({ms} ms)"


async def main() -> int:
    from app.agents import client as llm

    if not llm.credential_available():
        print("No Gemini credential found.")
        print("Add GEMINI_API_KEY=<your key> to backend/.env (copy backend/.env.example), or paste it in the app's Settings.")
        print("The game still runs in scripted mode without one.")
        return 0
    seen: set[str] = set()
    ok_all = True
    for role in ("suspect", "author", "guard"):
        ladder = llm.model_ladder(role)
        print(f"{role.upper()} ladder: {', '.join(ladder)}")
        for name in ladder:
            if name in seen:
                continue
            seen.add(name)
            ok, detail = await ping(name)
            ok_all &= ok
            print(f"  {'OK   ' if ok else 'ERROR'} {name:<28} {detail}")
    print("all configured models answered" if ok_all else "some models failed; the ladder will skip them at runtime")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
