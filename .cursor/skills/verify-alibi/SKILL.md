---
name: verify-alibi
description: >-
  Verify Murder Mystery Mayhem / Alibi boots and the scripted Vane Hall loop still
  works. Use when checking the repo after changes, before a demo, after setup, or
  when asked if the game works. Runs scripts/verify_alibi.sh against real servers.
  Also covers Vane Hall portrait/backdrop assets and MediaPipe CPU fallback tests.
---

# Verify Alibi

Run the harness. Do not declare the game healthy from unit tests alone.

## When to use

- After `make setup`, dependency changes, API/engine/frontend/sensor edits, or before a playtest.
- When someone asks "does the app work?" or "what is broken?"
- After camera / MediaPipe changes (GPU WebGL often fails; CPU fallback must stay covered).

## Command

From the repo root:

```bash
./scripts/verify_alibi.sh
```

Flags:

```bash
./scripts/verify_alibi.sh --skip-start    # servers already on :8000 and :5173
./scripts/verify_alibi.sh --quick        # tooling → assets → unit → health → api playtest → restart
./scripts/verify_alibi.sh --keep-servers # leave tmux sessions up after pass
```

Exit codes: `0` all gates passed, `1` a gate failed, `2` setup/environment blocked the run.

Logs: `.verify-alibi/` (gitignored) or `$VERIFY_ALIBI_OUT`.

## Gates (in order)

1. **Tooling.** `backend/.venv` and `frontend/node_modules` exist.
2. **Assets.** Vane Hall portrait + backdrop webps exist under `frontend/public/` (see gate body in the script).
3. **Unit.** Backend pytest (`-m "not integration"`) and frontend vitest including `faceLandmarker` CPU-fallback tests.
4. **Servers.** `GET /api/health` → `ok: true`. Frontend root → 200.
5. **API playtest.** `scripts/api_playtest.py` (scripted Vane Hall ask/search/present/flatter/search/confront/accuse/rewind; WS; Watson; no secret keys in game JSON).
6. **Restart persistence.** When this script started the backend: restart uvicorn; `GET /api/games/{id}` identical. Uses `.verify-alibi/verify.db`.
7. **Red team (full).** `LLM_MODE=scripted … redteam.py` → 0 FAIL.
8. **Frontend build (full).** `cd frontend && npm run build`.

`--quick` stops after gate 6.

## Camera / sensors (manual; not fully automatable here)

Harness proves the CPU-fallback *contract* in vitest. Live webcam needs a real browser:

1. Setup → tick 📷 → allow camera when prompted. Status must not stay on a raw `kGpuService` / WebGL error.
2. Begin → Investigation → Composure meter leaves "Camera off" within a few seconds with a face in frame.
3. Deny permission → status shows denial; game still playable.

## How to report

Print each gate as `PASS` / `FAIL` / `SKIP` with the log path. List open gaps the harness does **not** cover (browser WS paint, live Gemini, Author, immersive low-text UX). Never claim those are fine because the script exited 0.

## Related

- `docs/BROKEN.md`, `docs/FIX_PLAN.md`, `docs/IMMERSIVE_REDESIGN.md`
- `docs/DIAGNOSE_PLAYBOOK.md`, `PLAYTEST.md`
