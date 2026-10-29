# PROGRESS.md

## 2026-09-18 — M0 scaffold
- Repo created from PLAN.md; vane_hall.json copied to backend/app/cases; validate_case.py to scripts/.
- No Anthropic credential on this machine → decided LLM_MODE=auto with a deterministic scripted performer
  (docs/INTERFACES.md §0.1, §5) so the game is playable offline; live Claude suspects activate when a key is added.
- Models pinned: claude-sonnet-5 / claude-opus-5 / claude-haiku-4-5 (INTERFACES §0.2).
- UI branded "Murder Mystery Mayhem" per the owner's mockups (docs/DESIGN.md).
- Frontend scaffolded with Vite 8 + React 19 + Tailwind 4; backend venv with FastAPI 0.141, SQLAlchemy 2.0.54, anthropic 1.7.

## 2026-09-18 — provider switch
- Owner supplied a Gemini API key; provider is Google Gemini via google-genai 2.24 (INTERFACES §0.1–0.2). Anthropic
  SDK removed from the plan. Verified on the key: gemini-3.5-flash-lite / 3.1-flash-lite answer structured JSON in
  ~2 s; bigger flash models 503 under load; pro + image models 429 (quota). Model ladder + scripted fallback per turn.

## 2026-09-18 — provider switch to Gemini
- Owner supplied a Gemini API key and asked not to use Anthropic. Provider switched (docs/INTERFACES.md §0.1–0.4).
- Probe results on this key: gemini-2.5-* retired (404); pro + image models quota-blocked (429); 3.8/3.7/3.5-flash 503
  on every attempt; 3.6-flash works but slow (~25 s); 3.5-flash-lite / 3.1-flash-lite ~2 s with valid JSON.
  → model ladders in backend/.env.example; suspects default to gemini-3.5-flash-lite.
- Structured JSON output (response_json_schema) replaces forced tool use. Scripted performer remains the offline/fallback path.

## 2026-10-26 — diagnose + verify skill + fix plan
- Booted scripted mock_api + Vite on a clean image (needed `python3-venv`; npm needs `--legacy-peer-deps`).
- Measured: API Vane Hall loop works; 261 pytest + 27 vitest + redteam 120/120 pass; UI Setup→Briefing→Ask→Search→Judge→Debrief render.
- Broken inventory in `docs/BROKEN.md` (no persistent `main.py`, WS noop, Watson null, generate/api-key 404, rewind 501, boards/sensors missing, cast art vs Tapia gap).
- Added `.cursor/skills/verify-alibi`, `scripts/verify_alibi.sh`, `scripts/api_playtest.py`, `docs/FIX_PLAN.md`, `docs/DIAGNOSE_PLAYBOOK.md`.
- Decision trail: `docs/audit/diagnose-verify-plan.tsv` (committed).

## 2026-10-27 — FIX_PLAN Phase 1: persistent backend
- `backend/app/main.py` + config/db/models/schemas/routers/services replace `scripts/mock_api.py` (now deprecated,
  started by nothing). `make backend` / `make dev` run `app.main:app`; SQLite in `backend/alibi.db`.
- Commit-or-discard turns: each action runs the Director on a deep copy of the committed world, writes turn rows,
  snapshot, guard events and the suspect/evidence projection in one transaction, then adopts the copy. A failed
  action leaves the game untouched; GET and /debug never see half a turn and never wait on a running LLM turn.
- `turns.public` stores the PublicTurn per row so `GameState` is identical after a restart. The Director RNG is
  seeded per game and turn, so a restarted server rolls framing actions and tickers exactly as one that never
  stopped (`test_persistence.py` compares the two; an unseeded RNG fails it every run).
- Watson runs as a FastAPI background task after every 2nd player turn and every confrontation, from public turns,
  cast, evidence, locations and the public timeline only. A rewind bumps a branch counter so a late notebook from the
  old branch is dropped.
- Rewind archives rows after the chosen turn (turns, guard events, notebook entries, accusations) and restores that
  snapshot; a closed case reopens.
- Export is 404 unless `DEBUG_PANEL=1`. INTERFACES §6 calls it a share seed, but it carries the solution and PLAN
  §2.7 (non-negotiable) lets secrets out only behind that flag. No screen calls export yet.
- `call_tool` maps a missing key (`NotConfigured`) to `LLMUnavailable`, so `LLM_MODE=gemini` without a key falls back
  to scripted per turn instead of failing.
- WS sockets get the current clock on connect (a reconnecting client resyncs). `pending` is not sent; the client
  already shows its own pending state.
- Case generation answers 503 (no Gemini) / 501 (Author not built); `POST /tts` answers 501.
- `verify_alibi.sh` gate 5 restarts uvicorn and diffs `GET /api/games/{id}`; a started backend uses
  `.verify-alibi/verify.db`. All 7 gates pass; 279 pytest.

## 2026-10-27 — FIX_PLAN Phase 4: deduction boards
- Investigation right column is `NotebookPanel` (Notes, Alibi Board, Evidence, Graph). Accuse stays under it.
- Notes reads `GameState.notebook` (`per_suspect`, `suggested_next`, sticky). A null notebook still shows the last six turns.
- Alibi Board columns are the hours a claim covers. A public timeline hour is a column only when it falls inside a claim, so empty hours do not push the chips off a narrow panel. A chip is amber when both sides of a contradiction are the same suspect, red when the other side is someone else or a clue. A claim that only shares a clock with another claim stays plain. Identical claims are shown once.
- `GameState` has no relationship edges. The investigation graph is the cast plus confrontation lines the player heard (`PublicTurn` actor/other/spoken). Debrief `RumorMap` draws `rumor_map` with the same React Flow frame. Private edges animate. Confrontation edges are red.
- Evidence tab sets `useSensors.evidenceTabOpen` so a notebook gaze maps to evidence only while that tab is open.

## 2026-10-27 — FIX_PLAN Phases 0–4 shipped; Phase 5 held
- Phases 0–4 on `cursor/phases-0-4-11d9` (PR #2). Phase 5 graphics marked WAITING ON DESIGN — cast portraits,
  campaign map, confrontation chrome, demo MP4 after art direction; no generative filler faces until then.

## 2026-10-27 — Immersive redesign direction locked
- Owner rejected pixel faces; supplied noir / tabletop / crime-scene refs → `docs/art-direction/refs/`.
- Plan in `docs/IMMERSIVE_REDESIGN.md`: painted cast pack (owner delivers files), MediaPipe camera (free, no key),
  low-text arrive→crime→meet cast→room hotspots with the same verbs. FIX_PLAN Phase 5 unblocked as 5a–5e.

## 2026-10-28 — Phase 5a: painted Vane Hall portraits (neutral)
- Owner uploaded concept-board character pack (portraits + avatars + cards). Manifest notes alternate board names;
  UI uses label-free portraits only. Installed webp under `frontend/public/portraits/vane_hall/`.
- `PaintedPortrait` prefers pack art (avatar ≤64px, bust otherwise); missing emotion → `_neutral.webp`; else pixel fallback.
- Briefing / Investigation / Accuse / Debrief switched to PaintedPortrait. Backdrops still pending owner zip.

## 2026-10-28 — Phase 5a: Vane Hall backdrops
- Installed concept-board webps under `frontend/public/backdrops/{landscape_16x9,ultrawide_21x9,mobile_9x16,scene_originals}/`.
- `RoomBackdrop` uses responsive `<picture>`; Investigation follows the selected suspect's `last_seen_location`.
- Crime-scene / search modals use `BackdropThumb` (scene_originals). PNG sources omitted from the repo (webp only).

## 2026-10-28 — Briefing polish + live camera
- Removed Marquee logo from Briefing / Investigation / Debrief; briefing parchment wider; equal-height light
  suspect cards (no black lacquer); sticky notes use body serif not Caveat.
- Camera was a no-op: consent never called `start()`, face pipeline was a stub, ComposureMeter missing from
  Investigation. Consent checkbox now requests the webcam; MediaPipe FaceLandmarker samples composure/gaze;
  Investigation shows ComposureMeter and restarts the camera if consent was saved.

## 2026-10-28 — MediaPipe CPU fallback + verify skill
- GPU-only FaceLandmarker threw `kGpuService` / `emscripten_webgl_create_context() returned error 0`.
  `createLandmarkerWithFallback` tries GPU then CPU; vitest covers the WebGL failure path.
- `verify-alibi` skill + harness: asset gate, sensor vitest in unit gate, manual camera steps documented.

## 2026-10-28 — Story briefing (guided chapters)
- Replaced fact-sheet Briefing with click/key story: what happened → victim (+ time chip) →
  public timeline one beat at a time → meet each suspect in a claimed-room plate with a spoken intro →
  first evidence (decanter) → Begin investigation. Sticky note removed.
- Evidence object plates optional at `frontend/public/evidence/vane_hall/<id>.webp` (see EVIDENCE_ASSETS.md).

## 2026-10-28 — Confront label + click-to-collect rooms
- Suspect list Confront control is a high-contrast red ⚔ Confront button (opens Confront tab).
- Search opens RoomExplore: room backdrop + clue hotspots; `POST /search` with `evidence_id` examines
  one item. Locations carry `spots` (hidden clues unlabeled until collected).

## 2026-10-28 — Victim + brandy art drop
- Briefing victim chapter shows `/art/vane_hall/victim.webp` (crime scene).
- Decanter plate at `/evidence/vane_hall/decanter.webp` used in story first-evidence,
  Present chips, notebook Evidence tab, Accuse method chips, and room hotspots via `EvidenceArt`.

## 2026-10-28 — Transparent evidence pack
- Installed remapped webps for solicitor_letter, ledger, cyanide_jar, cigar_ash,
  cigar_case, necklace_clasp, torn_reference (zip names → case ids).
- Source pack kept under `docs/art-direction/vane_hall/evidence_source/`.
- Still missing plate: `ashes_in_grate` (dynamic).

## 2026-10-28 — Room search discoverability
- Location chips show glint counts; click opens the room immediately.
- Mystery hotspots are large pulsing gold “?” orbs (not invisible transparent art).
- Empty rooms (e.g. Drawing Room) point you to rooms that still have clues.

## 2026-10-28 — Confront icon + spots backend restart
- Confront control is icon-only (⚔) with hover “Confront”; left column a bit wider.
- “All clues collected” on every room was a stale uvicorn without `locations.spots`;
  restarted API so spots ship on GameState. Refresh / new game to see glints.

## 2026-10-28 — Hidden room objects (no spoiler UI)
- Room Search spots are plain evidence PNGs (no rings, glow, “?”, or glint counts).
- Location list no longer hints which rooms have clues.
- Spot anchors are per evidence id on desk/shelf/floor/mantel surfaces (cyanide ≠ ash).
- Landscape backdrops now serve pack PNG masters (not the over-compressed preview webps).
- Still missing evidence art: `ashes_in_grate` only.
