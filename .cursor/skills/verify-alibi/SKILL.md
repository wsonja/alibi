---
name: verify-alibi
description: >-
  Verify Murder Mystery Mayhem / Alibi boots and the scripted Vane Hall loop still
  works. Use when checking the repo after changes, before a demo, after setup, or
  when asked if the game works. Runs scripts/verify_alibi.sh gates against the
  real servers, not guesses.
---

# Verify Alibi

Run the harness. Do not declare the game healthy from unit tests alone.

## When to use

- After `make setup`, dependency changes, API/engine/frontend edits, or before a playtest.
- When someone asks "does the app work?" or "what is broken?"

## Command

From the repo root, with nothing else required if servers are down (the script can start them):

```bash
./scripts/verify_alibi.sh
```

Useful flags:

```bash
./scripts/verify_alibi.sh --skip-start    # servers already on :8000 and :5173
./scripts/verify_alibi.sh --quick        # health + pytest + api playtest only
./scripts/verify_alibi.sh --keep-servers # leave tmux sessions up after pass
```

Exit codes: `0` all gates passed, `1` a gate failed, `2` setup/environment blocked the run.

Logs land in `.verify-alibi/` (gitignored) or `$VERIFY_ALIBI_OUT` if set.

## Gates (in order)

1. **Tooling.** `backend/.venv` exists; `frontend/node_modules` exists. If missing, print `make setup` (needs `python3-venv` and `npm install --legacy-peer-deps` on this stack).
2. **Unit.** `cd backend && .venv/bin/python -m pytest -q -m "not integration"`.
3. **Servers.** `GET /api/health` → `ok: true`. `GET` frontend root → 200.
4. **API playtest.** `backend/.venv/bin/python scripts/api_playtest.py` (scripted Vane Hall ask/search/present/flatter/search/confront/accuse; forbids secret keys in game JSON).
5. **Red team (full mode).** `LLM_MODE=scripted backend/.venv/bin/python scripts/redteam.py --case backend/app/cases/vane_hall.json` → 0 FAIL.
6. **Frontend (full mode).** `cd frontend && npm test` and `npm run build`.

`--quick` stops after gate 4.

## How to report

Print each gate as `PASS` or `FAIL` with the log path. Then list open product gaps from `docs/BROKEN.md` that the harness does **not** cover (persistence, WS, Watson null, generate 404, graphics). Never claim those are fine because the script exited 0.

## Related docs

- `docs/BROKEN.md` — last measured inventory
- `docs/FIX_PLAN.md` — phased repair order
- `docs/DIAGNOSE_PLAYBOOK.md` — how that inventory was produced
- `PLAYTEST.md` — human guided route
- `docs/DESIGN.md` — visual contract
