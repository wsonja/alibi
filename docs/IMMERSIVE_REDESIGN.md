# Immersive redesign — art, camera, low-text flow

Owner direction (2026-10-27): kill pixel faces; noir / painterly **actual characters**; camera gaze that really works; far less reading; walk into the world, get the time + crime, meet people scene-by-scene, click around rooms; keep every investigation verb (ask, present, tactic, confront, search, accuse).

Refs locked in `docs/art-direction/refs/`:
1. Tabletop “Masters of Mystery” boxes + props desk (warm candlelight, wax seals, pocket watch)
2–4. Film-noir painted detective portraits (cyan rim / amber–teal chiaroscuro — **not** pixel)
5. Crime-scene still life (clapper, reel, knife, evidence markers, tape)

This supersedes the pixel-portrait path in `docs/DESIGN.md` §6 for faces. Room JPGs in `frontend/public/art/` stay until replaced by matching painted plates.

---

## A. What you (owner) need to do

### A1. Art — you supply or commission; we wire it

**No paid API required for graphics.** Do **not** paste random Midjourney faces one-by-one — they won’t match. Pick **one** pipeline and stick to it:

| Option | Cost | What you deliver |
|--------|------|------------------|
| **Commission** illustrator (best) | $–$$ | 5 Vane Hall cast × 6 emotion crops + 1 player detective optional |
| **One consistent AI pack** (Midjourney / Flux / Ideogram) with a locked style prompt from refs 02–04 | free tier / $ | Same file set; we reject one-off lottery faces |
| **Photo + paint pass** (Lightroom grade to amber/teal) | free | Only if rights-clear |

**File pack we need (Vane Hall first):**

```
frontend/public/portraits/vane_hall/
  margaret_{neutral,nervous,angry,smug,sad,afraid}.webp
  edmund_{…}.webp
  clarissa_{…}.webp
  thomas_{…}.webp
  ada_{…}.webp
```

- Bust / head-shoulders, **same crop box**, dark vignette, readable at 56px and 200px.
- Palette: deep teal/ink shadows, amber key or cyan rim (refs 02–04). No neon purple UI glow.
- Optional later: room plates that match (desk props like ref 01 / 05), campaign map art.

Drop the folder into the repo (or a Drive link) and say “portraits ready” — implementation swaps `PixelPortrait` → `<img>` / `PaintedPortrait` with emotion from game state.

### A2. Camera — almost nothing paid

**Free, browser-only (already in PLAN §11):**

| Piece | API / lib | Key? | Leaves device? |
|-------|-----------|------|----------------|
| Webcam | `getUserMedia` | no | no |
| Face + gaze + blink | `@mediapipe/tasks-vision` FaceLandmarker (WASM, Google) | **no** | **no** — models download once to the browser |
| Optional voice stress | Web Audio `AnalyserNode` | no | no |
| Optional TTS later | Web Speech API | no | no |

**You do:**

1. On Setup, leave **“Suspects will read your expression”** checked (or turn it on in settings).
2. Allow camera when the browser prompts (HTTPS or `localhost` only — Chrome blocks cam on plain HTTP LAN IPs sometimes).
3. Sit in decent light, face roughly toward the screen. No account, no Gemini key needed for sensors.
4. Optional: plug in a Gemini key only if you want **wittier** spoken lines; scripted mode still receives composure/gaze and can react once Block B is wired.

**We do:** replace the stub in `frontend/src/sensors/index.ts` (today it starts and emits **nothing**) with real MediaPipe sampling → `player_signal` on every ask/present/tactic/confront (already typed in the API).

### A3. Playtest machine

Keep playing from `~/Documents/alibi` on branch `cursor/phases-0-4-11d9` (or main once merged) until this redesign lands. Redesign work ships on follow-up PRs below — not required to “feel” Vane Hall today.

---

## B. Art system (build)

1. **Kill procedural pixels** as the default face (`PixelPortrait` stays only as fallback if a file is missing).
2. **`PaintedPortrait`**: loads `portrait_url` or convention path `portraits/{case}/{id}_{emotion}.webp`; emotion maps from `PublicSuspect.emotion`; dim/pending overlay stays.
3. **Confrontation**: dual painted busts + notes rail (Tapia + your noir duo ref).
4. **Chrome**: keep parchment/lacquer **or** shift Setup/Investigation toward “props on a desk” (ref 01) — clickable pocket-watch = clock, sealed envelope = case brief, magnifier = search. One visual language per case era (Vane Hall = warm candle + noir faces, not synthwave).
5. **Archive**: illustrated case map, not a bare list (still Phase 5 acceptance).

Acceptance: stranger comparing to refs 02–04 + Tapia slide 3 recognizes the same product; zero pixel faces on the happy path.

---

## C. Camera / gaze (build) — PLAN M4

Current: consent UI + composure meter shell exist; `sensors/index.ts` is a **placeholder**.

Ship order:

1. Load FaceLandmarker WASM from jsDelivr / Google CDN (or vendored); ~15 fps, sample every ~2 s.
2. Map blendshapes → `composure` + `gaze` exactly as PLAN §11 (`suspect` | `evidence` | `notebook` | `away`).
3. Attach `player_signal` on turn POSTs; Block B already has observation phrasing in PLAN.
4. UI: live composure meter + tiny privacy line “Video never leaves your device.”
5. Off path unchanged (PLAN §2.6) — game fully playable with camera denied.

Acceptance: looking at Evidence while asking → Judge/`internal_reasoning` mentions the glance; camera off → no `player_signal`.

**No free cloud “eye API”** is better than on-device MediaPipe for privacy + cost. Skip WebGazer unless MediaPipe gaze proves too weak.

---

## D. Low-text immersive flow (build) — new UX layer

**Principle:** show the world first; text is captions, not homework. All verbs stay reachable without a wall of instructions.

### D1. Session spine (replace Setup → Briefing wall)

| Beat | Player sees | Reads | Does |
|------|-------------|-------|------|
| 1. Arrive | Full-bleed room / manor night | Brand + one line (“A body. One night. Four stories.”) | Click into the house |
| 2. Time + crime | Pocket watch + crime-scene plate (ref 05 energy) | **Clock range** + **one sentence** what happened + where | Tap Continue |
| 3. Meet the cast | Walk room → room; each suspect enters in place | Name + role only; alibi as **spoken** line, not a paragraph | Click person to listen / follow |
| 4. Free roam | Hotspots in the current room (desk, bottle, door, person) | Tooltip ≤6 words | Click → search / examine / talk |
| 5. Always-on verbs | Radial or dock: Ask · Present · Tactic · Confront · Search · **Accuse** | Icon-first labels | Same API actions as today |

Briefing’s long narrative moves to optional “Case file” drawer (envelope prop), not the front door.

### D2. Investigation layout (less panel, more room)

- **Centre = room stage** (painted plate + hotspots + active suspect).
- Dialogue: last line big; full log collapsed behind “Transcript”.
- Notebook: icon drawer (Notes / Alibi / Evidence / Graph) — not a permanent essay column.
- Suspect list: portraits strip; pressure as a thin ring, not a labeled essay.
- Confront / Accuse: keep current power, restyle chrome; Accuse available **anytime** from the dock (already keyboard `A` — make the control obvious).

### D3. Copy diet

- Kill instructional subtitles that repeat the control (“Ask a question”, “Change approach”) once icons are clear.
- Watson notes: max 3 bullets visible; rest in “more”.
- Ticker: one short event, not a crawl of prose.

### D4. Keep every function

| Verb | How in new UX |
|------|----------------|
| Ask | Select person → Ask (mic optional later) |
| Present | Select evidence chip / bag → Present to person |
| Tactic | Flatter / Bluff / Threaten / Silence on dock |
| Confront | Select two portraits (or Confront + pick second) |
| Search | Click room hotspot or Search + location |
| Accuse | Dock / `A` anytime |
| Rewind / settings / a11y | Gear menu; low-sensory still strips motion |

Engine + API unchanged; this is presentation + hotspot mapping onto existing endpoints.

---

## E. Suggested build order (after phases 0–4 merge)

| Step | PR theme | Depends on you? |
|------|----------|-----------------|
| **5a** | Art direction lock + `PaintedPortrait` + drop-in Vane Hall pack | **Yes — portrait files** |
| **5b** | Immersive spine (arrive → time/crime → meet cast → roam) + action dock | No (can use temp portraits) |
| **5c** | Room hotspots → search/examine | Case location/evidence IDs |
| **5d** | MediaPipe sensors live + meter | Camera on your laptop to QA |
| **5e** | Archive map art + demo MP4 | Optional campaign illustration |

Phase 6 voice/heartbeat stays after 5d if presence still feels thin.

---

## F. Out of scope (for now)

- Procedural Author (Phase 7)
- Uploading webcam frames to any server
- Replacing room JPGs before cast faces exist
- Paying for a cloud vision API

---

## G. Decision log

- Pixel faces are rejected; noir painted busts are the north star (owner refs 2026-10-27).
- Sensors stay on-device MediaPipe (free); stub must go.
- UX goal is imperative immersion with the same verbs, not a new ruleset.
