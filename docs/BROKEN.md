# What works and what does not

Measured on 2026-10-26 (America/New_York) against `main` tip `0cd1c07`, branch `cursor/diagnose-verify-plan-11d9`.
Servers: `scripts/mock_api.py` on `:8000` with `LLM_MODE=scripted`, Vite on `:5173`.

**Evidence kinds.** `[runtime]` means a command, HTTP call, or screenshot was run this session. `[code]` means read from source or docs, not exercised live. Artifact paths under `/opt/cursor/artifacts/smoke/` exist on the agent VM only. Re-run `./scripts/verify_alibi.sh` for fresh logs in `.verify-alibi/`.

## Works (verified)

| Check | Evidence |
| --- | --- |
| Backend health | `[runtime]` `GET /api/health` → `ok:true`, 4 cases, `llm_mode:scripted` |
| Frontend serves | `[runtime]` `GET http://127.0.0.1:5173/` → 200; Setup shows case tiles (`smoke/browser/01-setup.png`) |
| Scripted Vane Hall loop (HTTP) | `[runtime]` ask → search → present → flatter → confront → accuse correct Inspector |
| Unit tests | `[runtime]` `make test` → **261 passed**, 2 deselected |
| Frontend tests + build | `[runtime]` vitest **27 passed**; `npm run build` OK |
| Isolation red-team (scripted) | `[runtime]` `scripts/redteam.py` Vane Hall → **120 pass, 0 FAIL** |
| Briefing / Investigation / Judge / Debrief UI | `[runtime]` screenshots `03`–`05`, `09`, `10` under `smoke/browser/` |
| Search finds evidence in UI | `[runtime]` Search Billiard Room opens "New evidence" modal |
| Judge panel | `[runtime]` backtick opens `/debug` UI (`smoke/browser/09-judge-panel.png`) |
| Reveal reel on Debrief | `[runtime]` after accuse (`smoke/browser/10-debrief.png`) |

## Broken or incomplete

### Boot and tooling

1. **`make setup` fails without `python3-venv`.** `[runtime]` `ensurepip` missing. Log: `smoke/make-setup.log`. Makefile now guards and prints the apt hint.
2. **Plain `npm install` fails on peer deps** (`typescript@6` vs `openapi-typescript@7` wanting `^5`). `[runtime]` failure is in `smoke/make-setup.log` (the successful retry used `--legacy-peer-deps` and logged to `smoke/npm-install.log`). Makefile setup now passes `--legacy-peer-deps`. Pinning versions is still the durable fix (FIX_PLAN Phase 0).
3. **Makefile still points at the temporary API.** `[code]` `make backend` runs `mock_api:app`. There is **no** `backend/app/main.py` (PLAN §3). Health `note` says TEMPORARY.

### Persistence and API surface

4. **Games are in-memory only.** `[runtime]` create game → restart uvicorn → same `game_id` returns 404 (`smoke/restart-wipe.log`). Contradicts PLAN §2.5 / M1 accept.
5. **`POST /api/games/{id}/rewind` returns 501.** `[runtime]` + `[code]` stub in `scripts/mock_api.py`. Playtest prints `GAP rewind_not_implemented`.
6. **Missing endpoints the frontend already calls.** `[runtime]` 404s: `POST /api/cases/generate`, `GET /api/cases/jobs/:id`, `POST /api/settings/api-key`. Import/export also absent on mock_api (`[code]`).
7. **WebSocket is a black hole.** `[code]` `/api/ws/games/{id}` accepts then only `receive_text` loops. No event pushes.
8. **Watson notebook is always `null` in game state.** `[runtime]` + `[code]` `mock_api.state()` hardcodes `"notebook": None`.
9. **Leak Guard path in mock is regex-only.** `[code]` `guard()` calls `leak_guard.regex_check` only.
10. **Planned tests missing.** `[code]` no `test_api.py`, `test_persistence.py`, or `test_leaks.py` (PLAN §15).

### Gameplay fun / scripted quality

11. **PLAYTEST “Pell admits the study after cigar present” fails in scripted mode.** `[runtime]` After present, ask “Where did you really go?” returns a Margaret wet-shoes pivot. Spoken text has no “study”. Stress still rises. Playtest now prints `GAP ask_after_present_no_study_admit` (does not fail the harness until Phase 2 hardens scripted).
12. **Accuse method picker ignores `known` evidence.** `[runtime]` brandy starts `known`; modal filters `examined` only (`Investigation.tsx`).
13. **“Your room” / generate needs an API-key path that 404s.** `[runtime]` settings route missing.

### Features promised in PLAN / Tapia deck, not shipped

14. **No Alibi Board, Relationship Graph, or Rumor Map UI.** `[code]` `@xyflow/react` unused under `frontend/src`.
15. **Sensors / composure / voice / heartbeat are placeholders.** `[code]` files say so; `ComposureMeter` never mounted; `useSensors.start` never called from screens.
16. **Archive is a thin list.** `[code]` `Archive.tsx` still says placeholder. No campaign map.
17. **Character art is procedural pixel portraits.** `[runtime]` screenshots + `[code]` `pixelPortrait.ts`. Room JPGs in `public/art/` are painted backdrops (full fake UIs under a blur), not clickable widgets.
18. **Tapia slide 4 has a demo-video hole.** `[code]` slide image in `docs/reference/slide-4.png`.
19. **Provider story drifted.** `[code]` deck says Claude; repo is Gemini + scripted (`docs/INTERFACES.md` §0).

### Isolation / judge gaps

20. **F9 does not toggle Judge.** `[code]` Investigation listens for backtick (and A for Accuse). Keycap UI claims F9.
21. **Cross-contamination field is always empty.** `[code]` mock debug hardcodes `"cross_contamination": []`.
22. **`DEBUG_PANEL` is ignored.** `[code]` mock `/debug` always returns secrets. PLAN §9 says 404 unless `DEBUG_PANEL=1`.
23. **Snapshots are never stored on turns.** `[code]` `snapshot.take` unused by mock_api.
24. **`LLM_MODE=gemini` without a key can stall.** `[code]` `Director` only catches `LLMUnavailable` by class name; missing-key `NotConfigured` is not that name.
25. **Author/Checker have no HTTP job surface.** `[code]` modules exist; PersonaHub sample file missing.
26. **Dialogue log ignores speaker colors.** `[code]` every row hardcodes `speaker-0` in `Investigation.tsx`.
27. **Confront UI is tab-only.** `[code]` store has `interject` / `justWatch`; no dual-portrait stage.
28. **`frontend/FOUNDATION.md` is stale.** `[code]` still calls Investigation/Debrief/Judge placeholders. Do not rebuild them from that doc.

## False alarms ruled out

- Substring `"solution"` in game JSON was a hit on **"dissolution"** in evidence text, not a leaked `solution` key. Verification checks JSON keys.
- npm peer failure must be cited from `make-setup.log`, not from the later successful `--legacy-peer-deps` install log.
