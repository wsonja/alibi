# Fix plan: fun, functional Murder Mystery Mayhem

Goal: a judge can follow `PLAYTEST.md`, feel a mystery, and see the Tapia isolation story (Judge panel + reveal reel) without fighting the stack.

Visual north star for **rooms and chrome**: painted desk/study art already in `frontend/public/art/` plus `docs/DESIGN.md` (parchment / lacquer / Cinzel).  
Visual north star for **cast**: Tapia slide 3 illustrated portraits (hand-authored or commissioned), not more generative "AI face" sludge and not only the current procedural pixels.

Do phases in order. Each phase ends with `scripts/verify_alibi.sh` green plus that phase's acceptance line.

## Phase 0. Make boot boring

**Why first.** Foundational. Nothing else is re-runnable until `make setup` works on a clean machine.

- Install docs: require Python 3.12 + `python3-venv` + Node 20.
- Makefile `setup`: create venv, `pip install -r requirements`, `npm install --legacy-peer-deps`, copy `.env.example`.
- Optional: pin `openapi-typescript` or TypeScript so peers resolve without a flag.
- Acceptance: fresh clone → `make setup` → `make backend` + `make frontend` → health 200 and Setup renders.

## Phase 1. Persist the real backend

**Why.** In-memory `mock_api` is why "the app never actually worked" across demos. Restart kills the case.

- Land `backend/app/main.py` + routers per `docs/INTERFACES.md` / PLAN §9.
- SQLite `alibi.db`, call `snapshot.take` and write it on every turn before the response (PLAN §2.5).
- Gate `/debug` on `DEBUG_PANEL=1`.
- Wire Watson notebook into `GameState.notebook` (stop hardcoding `null`; call `watson.update`).
- WebSocket fan-out for turn / confront / ticker / notebook events.
- Make missing-key Gemini resolve to scripted (or map `NotConfigured` → `LLMUnavailable`) so `LLM_MODE=gemini` never stalls a turn.
- Implement or clearly hide: rewind, settings/api-key, generate/import/export.
- Delete or demote `mock_api` once parity exists.
- Add `test_api.py` + `test_persistence.py` (PLAN §15).
- Acceptance: kill uvicorn mid-game, restart, `GET /games/{id}` resumes; WS events update the Investigation UI without refresh.

## Phase 2. Make the guided mystery fun offline

**Why.** Scripted mode must teach the game when Gemini is down. Today Pell never "admits the study" on the PLAYTEST line.

- Harden `agents/scripted.py` against `PLAYTEST.md` beats (cigar → study admit, Ada a3 after two flatters, framing burn).
- Accuse modal: allow method picks from `known` **or** `examined` (brandy starts known).
- Surface ticker / off-screen gossip text so the house feels alive.
- Keep Leak Guard regex path honest in scripted mode; log guard events into Judge + reel.
- Acceptance: a human (or Playwright) following `PLAYTEST.md` in scripted mode reaches Correct / Detective+.

## Phase 3. Live suspects without breaking isolation

**Why.** Tapia pitch is multi-agent secrets under pressure.

- Gemini key via `POST /settings/api-key` writing `backend/.env` only.
- Full Leak Guard (regex ∪ model) with regenerate / fallback (PLAN §7.4).
- `make redteam` green in scripted **and** a recorded gemini sample run.
- Judge Context Boxes show per-suspect system blocks with no foreign secrets.
- Acceptance: red-team 0 FAIL; human judge confirms a locked secret stayed locked under prompts 1–15.

## Phase 4. Boards that make deduction tactile

**Why.** Ask/present alone feels like a chatbot. Tapia + PLAN M2–M3 need spatial tools.

- Alibi Board (time grid, contradiction highlight).
- Relationship Graph + Rumor Map via `@xyflow/react`.
- Watson contradictions drive "Working notes" and sticky suggestions.
- Acceptance: after asking Margaret and Crane about 23:00–23:30, the Alibi Board marks the overlap without opening debug.

## Phase 5. Graphics pass (non-AI look)

**Why.** Setup already uses strong painted backdrops. Suspect faces and campaign art are the weak link vs slide 3.

- Keep room JPGs; do **not** replace them with flat purple gradients or stock AI collage.
- Commission or hand-draw 4–5 cast portraits × emotion variants (or refine pixel set to a consistent limited palette with readable silhouettes). Ban one-off generative faces that don't share a palette.
- Campaign / Archive screen: illustrated case map matching slide 3 (First Murder → Death at Sea → Pitch → Heiress), not a bare list.
- Confrontation layout: dual portraits + notes rail as in slide 3 left panel.
- Capture a real demo MP4 for slide 4 / README.
- Acceptance: side-by-side with Tapia slide 3, a stranger can tell it is the same product; no "AI portrait lottery" look.

## Phase 6. Presence layers (optional, after core fun)

Sensors, voice STT/TTS, heartbeat, dyslexia / low-sensory polish (PLAN M4–M5, M8).  
Acceptance: game fully playable with every sensor off (already required by PLAN §2.6); with sensors on, composure affects stress deltas observably in Judge.

## Phase 7. Author / campaign / multiplayer (later)

Procedural Author+Checker (M6), rewind+cast_memory (M7), multiplayer (M9). Only after Phases 0–5 delight a single-player Vane Hall run.

## Suggested PR stack

1. `chore: make setup reliable` (Phase 0)
2. `feat: persistent FastAPI backend + watson + ws` (Phase 1)
3. `fix: scripted PLAYTEST path + accuse known evidence` (Phase 2)
4. `feat: gemini leak guard + api-key settings` (Phase 3)
5. `feat: alibi board + relationship/rumor graphs` (Phase 4)
6. `feat: cast art + campaign archive visuals + demo video` (Phase 5)

Each PR must keep `.cursor/skills/verify-alibi` green.
