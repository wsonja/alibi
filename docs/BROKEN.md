# What works and what does not

Measured on 2026-10-26 (America/New_York) against `main` tip `0cd1c07`, branch `cursor/diagnose-verify-plan-11d9`.
Servers: `scripts/mock_api.py` on `:8000` with `LLM_MODE=scripted`, Vite on `:5173`.
Evidence under `/opt/cursor/artifacts/smoke/` (and committed pointers below).

## Works (verified)

| Check | Evidence |
| --- | --- |
| Backend health | `GET /api/health` → `ok:true`, 4 cases, `llm_mode:scripted` (`smoke/api-playtest.log`) |
| Frontend serves | `GET http://127.0.0.1:5173/` → 200; Setup shows marquee + case tiles (`smoke/browser/01-setup.png`) |
| Scripted Vane Hall loop | ask → search billiard → present → flatter Ada ×2 → search darkroom/study → confront → accuse correct Inspector (`smoke/api-playtest.log`) |
| Unit tests | `make test` → **261 passed**, 2 deselected (`smoke/pytest.log`) |
| Frontend tests + build | vitest **27 passed**; `npm run build` OK (`smoke/vitest.log`, `smoke/frontend-build.log`) |
| Isolation red-team (scripted) | `scripts/redteam.py` Vane Hall → **120 pass, 0 FAIL** (`smoke/redteam.log`) |
| Briefing / Investigation / Judge / Debrief UI | screenshots `03`–`05`, `09`, `10` under `smoke/browser/` |
| Search finds evidence in UI | Search Billiard Room opens "New evidence" modal (Playwright intercept log) |

## Broken or incomplete (with evidence)

### Boot and tooling

1. **`make setup` fails on a clean Ubuntu image without `python3-venv`.** `ensurepip` missing. Fix: install `python3.12-venv` (or document it). Log: `smoke/make-setup.log`.
2. **`npm install` fails on peer deps** (`typescript@6` vs `openapi-typescript@7` wanting `^5`). Needs `--legacy-peer-deps`. Log: `smoke/npm-install.log`.
3. **Makefile still points at the temporary API.** `make backend` runs `mock_api:app`. There is **no** `backend/app/main.py` (PLAN §3). README admits this.

### Persistence and API surface

4. **Games are in-memory only.** Restarting the backend wipes every game. Contradicts PLAN §2.5 and M1 accept ("kill backend, resume").
5. **`POST /api/games/{id}/rewind` returns 501.** Explicit stub in `scripts/mock_api.py`.
6. **Missing endpoints the frontend already calls:**
   - `POST /api/cases/generate` → 404
   - `GET /api/cases/jobs/:id` → 404
   - `POST /api/settings/api-key` → 404
   - case import/export routes not on mock_api
7. **WebSocket is a black hole.** `/api/ws/games/{id}` accepts then only `receive_text` loops. No `turn_result`, `confront_line`, `ticker`, or `notebook_updated` pushes. Frontend store is ready for them.
8. **Watson notebook is always `null` in game state.** `mock_api.state()` hardcodes `"notebook": None` even though `director` builds `watson_visible`. Investigation "Working notes" are a local heuristic, not Watson.
9. **Leak Guard path in mock is regex-only.** `guard()` calls `leak_guard.regex_check` only, not the Gemini union path. Fine for scripted offline, not the Tapia "Leak Guard" story.
10. **Planned tests missing:** no `test_api.py`, `test_persistence.py`, or `test_leaks.py` (PLAN §15). Engine tests exist.

### Gameplay fun / scripted quality

11. **PLAYTEST step "Pell admits the study after cigar present" fails in scripted mode.** After presenting `cigar_case`, ask "Where did you really go?" returns a pivot about Margaret's wet shoes, not an admission (`smoke/api-playtest.log` `ask_after_present`). Stress does rise (7%→36%). Live Gemini may differ. Scripted path is not a reliable guided tutorial.
12. **Accuse method picker ignores `known` evidence.** Initial brandy is `known`, not `examined`. Accuse modal only lists `examined` (`Investigation.tsx` `examined` filter). Player can accuse with empty method until they search rooms. Confirmed via API state dump.
13. **"Your room" / generate tile needs an API key path that 404s.** Setup shows "NEEDS API KEY" but paste-key endpoint is missing, so generation cannot work on mock_api.

### Features promised in PLAN / Tapia deck, not shipped

14. **No Alibi Board, Relationship Graph, or Rumor Map UI.** `@xyflow/react` is in `package.json` but unused in `src/`. Tapia slide 3 and PLAN M2–M3 require them.
15. **Sensors / composure / voice / heartbeat are placeholders.** Files say so: `frontend/src/sensors/index.ts`, `voice/index.ts`, `audio/heartbeat.ts`, `components/sensors/*`. Camera checkbox on Setup does not drive real MediaPipe.
16. **Archive is a thin list**, still marked placeholder (`Archive.tsx`). No campaign map like Tapia slide 3 right panel.
17. **Character art is procedural pixel portraits**, not the painted cast from the Tapia mockups. Painted **room** backdrops exist (`frontend/public/art/*.jpg`) and look intentional. Suspect faces do not match the slide-3 illustrated cast.
18. **Tapia slide 4 still has a demo-video hole.** No recorded playthrough in-repo for judges.
19. **Provider story drifted.** Deck says Claude Sonnet/Haiku/Opus. Repo runs Gemini + scripted fallback (`docs/INTERFACES.md` §0). Architecture (one call per suspect, Director deterministic) matches. Marketing copy on the deck is stale.

### Isolation / judge story (partial)

20. **Judge panel works** on backtick against `/debug` (`smoke/browser/09-judge-panel.png`). Good for the Tapia proof story. The UI shows an F9 keycap but Investigation only listens for backtick (and A for Accuse). F9 does nothing.
21. **Cross-contamination field is always empty** in mock debug (`"cross_contamination": []` hardcoded). Not computed.
22. **Reveal reel works on Debrief** after accuse (`smoke/browser/10-debrief.png`).
23. **`DEBUG_PANEL` is ignored.** Mock `/debug` always returns secret text, heard logs, and internal reasoning. PLAN §9 says that route should 404 unless `DEBUG_PANEL=1`.
24. **Snapshots are never stored on turns.** `engine/snapshot.py` exists and unit tests call `take`, but `mock_api` never persists a snapshot. Restart resume is impossible even if you kept the process id.
25. **`LLM_MODE=gemini` without a key does not fall back.** `resolve_mode("gemini")` still returns gemini. `Director` only catches exceptions named `LLMUnavailable`. A missing-key `NotConfigured` from the client propagates and stalls the turn. Measured from `performer.py` / `director.py` exception-name branch.
26. **Author and Checker modules exist** (`agents/author.py`, `checker.py`) but have no HTTP job surface and no PersonaHub sample file. Generation UI is ahead of the server.
27. **Dialogue log ignores speaker colors.** Every row hardcodes `speaker-0` in `Investigation.tsx`. `speakerIndex` exists on the store and is unused.
28. **Confront UI is tab-only.** Store has `interject` and `justWatch`. No dual-portrait confrontation stage, no interject control, no “Just watch”. Tapia slide 3 left panel is not built.
29. **`ComposureMeter` is never mounted.** Sensors store `start()` is never called from screens. Camera consent only flips a flag.
30. **`frontend/FOUNDATION.md` is stale.** It still calls Investigation, Debrief, and Judge placeholders. Those screens are real (Archive is the remaining thin placeholder). Do not rebuild them from that doc.

## False alarms ruled out

- Substring `"solution"` in game JSON was a hit on **"dissolution"** in evidence text, not a leaked `solution` key. Verification must check JSON keys, not substrings.
- The painted JPEGs in `frontend/public/art/` are full mockup screens used as blurred backdrops. They are not clickable widgets. Live UI is React + procedural pixels on top.
