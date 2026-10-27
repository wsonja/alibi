# What works and what does not

Measured on 2026-10-26 (America/New_York) against `main` tip `0cd1c07`, branch `cursor/diagnose-verify-plan-11d9`.
Servers: `scripts/mock_api.py` on `:8000` with `LLM_MODE=scripted`, Vite on `:5173`.

**Update 2026-10-27 (FIX_PLAN Phase 1, branch `cursor/phases-0-4-11d9`).** `backend/app/main.py` replaced the mock.
Items it fixed moved to "Fixed in Phase 1" below with their original numbers.

**Evidence kinds.** `[runtime]` means a command, HTTP call, or screenshot was run this session. `[code]` means read from source or docs, not exercised live. Artifact paths under `/opt/cursor/artifacts/smoke/` exist on the agent VM only. Re-run `./scripts/verify_alibi.sh` for fresh logs in `.verify-alibi/`.

## Works (verified)

| Check | Evidence |
| --- | --- |
| Backend health | `[runtime]` `GET /api/health` → `ok:true`, 4 cases, `llm_mode:scripted` |
| Frontend serves | `[runtime]` `GET http://127.0.0.1:5173/` → 200; Setup shows case tiles (`smoke/browser/01-setup.png`) |
| Scripted Vane Hall loop (HTTP) | `[runtime]` ask → search → present → flatter → confront → accuse correct Inspector |
| Unit tests | `[runtime]` `make test` → **261 passed**, 2 deselected (**279** after Phase 1) |
| Frontend tests + build | `[runtime]` vitest **27 passed**; `npm run build` OK |
| Isolation red-team (scripted) | `[runtime]` `scripts/redteam.py` Vane Hall → **120 pass, 0 FAIL** |
| Briefing / Investigation / Judge / Debrief UI | `[runtime]` screenshots `03`–`05`, `09`, `10` under `smoke/browser/` |
| Search finds evidence in UI | `[runtime]` Search Billiard Room opens "New evidence" modal |
| Judge panel | `[runtime]` backtick opens `/debug` UI (`smoke/browser/09-judge-panel.png`) |
| Reveal reel on Debrief | `[runtime]` after accuse (`smoke/browser/10-debrief.png`) |

## Fixed in Phase 1 (2026-10-27)

| # | Was | Evidence now |
| --- | --- | --- |
| 3 | Makefile ran `mock_api:app`; no `main.py` | `[runtime]` `make backend` runs `app.main:app`; health has no TEMPORARY note |
| 4 | Games in memory only | `[runtime]` verify gate 5: Ctrl-C uvicorn, restart, `GET /api/games/{id}` identical. `[runtime]` browser reload after restart shows every turn. `test_persistence.py` also proves a restarted server plays on exactly like an uninterrupted one |
| 5 | Rewind 501 | `[runtime]` playtest `rewind_reopens_turn_1`, `debrief_gone_after_rewind` |
| 6 | api-key, generate, jobs, import, export missing | `[runtime]` `test_api.py`: api-key writes `backend/.env` and switches auto→gemini; import runs `static_check`; generate answers 503 without Gemini (501 with it: the Author is not built); export exists behind `DEBUG_PANEL` (see 22) |
| 7 | WebSocket pushed nothing | `[runtime]` playtest `ws_pushes_turn_result`, `ws_pushes_notebook`; headless Chromium showed pushed replies on `/game/{id}` without a reload |
| 8 | Watson notebook always null | `[runtime]` playtest `watson_notebook_in_game_state` (after every 2nd turn and every confrontation) |
| 9 | Mock Leak Guard regex-only | `[code]` the app calls `leak_guard.check(spoken, locked, mode)`: regex in scripted, regex ∪ model in gemini |
| 21 | cross_contamination always `[]` | `[code]` computed from each suspect's last system blocks; `test_api.py` plants a leak and sees it flagged |
| 22 | `DEBUG_PANEL` ignored | `[runtime]` `/debug` and `/cases/{id}/export` are 404 unless `DEBUG_PANEL=1` |
| 23 | Snapshots never stored | `[code]` `snapshot.take` on the last turn row of every action, written before the response |
| 24 | `LLM_MODE=gemini` without a key stalls | `[runtime]` `test_gemini_mode_without_a_key_still_plays_every_turn` (fails without the fix) |

Partly fixed: **10** (`test_api.py` and `test_persistence.py` exist; `test_leaks.py` does not), **13** (the api-key
route works; case generation itself is still unbuilt).

## Broken or incomplete

### Boot and tooling

1. **`make setup` fails without `python3-venv`.** `[runtime]` `ensurepip` missing. Log: `smoke/make-setup.log`. Makefile now guards and prints the apt hint.
2. **Plain `npm install` fails on peer deps** (`typescript@6` vs `openapi-typescript@7` wanting `^5`). `[runtime]` failure is in `smoke/make-setup.log` (the successful retry used `--legacy-peer-deps` and logged to `smoke/npm-install.log`). Makefile setup now passes `--legacy-peer-deps`. Pinning versions is still the durable fix (FIX_PLAN Phase 0).
### Persistence and API surface

10. **Planned tests partly missing.** `[code]` `test_leaks.py` (PLAN §15) does not exist yet.

### Gameplay fun / scripted quality

11. **PLAYTEST “Pell admits the study after cigar present” fails in scripted mode.** `[runtime]` After present, ask “Where did you really go?” returns a Margaret wet-shoes pivot. Spoken text has no “study”. Stress still rises. Playtest now prints `GAP ask_after_present_no_study_admit` (does not fail the harness until Phase 2 hardens scripted).
12. **Accuse method picker ignores `known` evidence.** `[runtime]` brandy starts `known`; modal filters `examined` only (`Investigation.tsx`).
13. **“Your room” cannot generate a case.** `[runtime]` the api-key route works, but `POST /api/cases/generate` answers 503 without Gemini and 501 with it: the Author job surface (25) is not built.

### Features promised in PLAN / Tapia deck, not shipped

14. **FIXED 2026-10-27. Alibi Board, Relationship Graph, and Rumor Map.** Notebook tabs on Investigation. Rumor map on Debrief. `@xyflow/react` draws both graphs. Case relationships are not on `GameState`, so the investigation graph uses confrontation lines the player heard.
15. **Sensors / composure / voice / heartbeat are placeholders.** `[code]` files say so; `ComposureMeter` never mounted; `useSensors.start` never called from screens.
16. **Archive is a thin list.** `[code]` `Archive.tsx` still says placeholder. No campaign map.
17. **Character art is procedural pixel portraits.** `[runtime]` screenshots + `[code]` `pixelPortrait.ts`. Room JPGs in `public/art/` are painted backdrops (full fake UIs under a blur), not clickable widgets.
18. **Tapia slide 4 has a demo-video hole.** `[code]` slide image in `docs/reference/slide-4.png`.
19. **Provider story drifted.** `[code]` deck says Claude; repo is Gemini + scripted (`docs/INTERFACES.md` §0).

### Isolation / judge gaps

20. **F9 does not toggle Judge.** `[code]` Investigation listens for backtick (and A for Accuse). Keycap UI claims F9.
25. **Author/Checker have no HTTP job surface.** `[code]` modules exist; PersonaHub sample file missing.
26. **Dialogue log ignores speaker colors.** `[code]` every row hardcodes `speaker-0` in `Investigation.tsx`.
27. **Confront UI is tab-only.** `[code]` store has `interject` / `justWatch`; no dual-portrait stage.
28. **`frontend/FOUNDATION.md` is stale.** `[code]` still calls Investigation/Debrief/Judge placeholders. Do not rebuild them from that doc.

## False alarms ruled out

- Substring `"solution"` in game JSON was a hit on **"dissolution"** in evidence text, not a leaked `solution` key. Verification checks JSON keys.
- npm peer failure must be cited from `make-setup.log`, not from the later successful `--legacy-peer-deps` install log.
