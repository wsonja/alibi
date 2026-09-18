# INTERFACES.md — module contracts (read with PLAN.md; this refines it)

PLAN.md is the spec. This file pins the concrete Python/TypeScript interfaces so lanes built in parallel fit
together, and records the decisions taken at M0. Where this file and PLAN.md differ, this file wins.

## 0. Decisions taken at M0 (2026-09-18)

1. **LLM provider is Google Gemini, not Anthropic.** The owner asked for Gemini. PLAN.md says "Claude" everywhere;
   read every "Claude call" in PLAN.md as "Gemini call". The architecture (one call per suspect per turn, strict
   context isolation, structured output, Leak Guard, deterministic Director) is unchanged. `agents/` is the only
   package that imports `google.genai` (SDK `google-genai` 2.24, installed in backend/.venv).
2. **LLM mode.** `LLM_MODE=auto|gemini|scripted`. `auto` (default) = `gemini` when `GEMINI_API_KEY` (or
   `GOOGLE_API_KEY`) is set, else `scripted`. `scripted` is a deterministic, rule-based performer
   (`agents/scripted.py`) that plays every suspect from its case data alone, so the whole game is playable offline. It
   obeys exactly the same isolation rules (it only ever sees its own suspect dict + its own state). `FAKE_LLM=1` from
   PLAN.md is an alias for `LLM_MODE=scripted`. Tests run in scripted mode. In gemini mode, if a call fails after the
   fallback ladder, the Director uses the scripted performer for that turn and records a guard event
   `provider_fallback` (the game never stalls on the API).
3. **Models** (verified against this key on 2026-09-18 with `GET /v1beta/models`): gemini-2.5-* are retired for new
   keys (404); `gemini-3.1-pro-preview`, `gemini-pro-latest` and the image models are quota-blocked (429) on this key;
   `gemini-3.8-flash` / `3.7-flash` / `3.5-flash` returned 503 "high demand" on every probe; `gemini-3.6-flash` works
   but is slow (~25 s with thinking); `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` answer valid JSON in ~2 s.
   Therefore each role has a **fallback ladder** (comma-separated env vars, first is preferred):
   `SUSPECT_MODEL=gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.6-flash` (suspects, Watson),
   `AUTHOR_MODEL=gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite` (Author, Checker),
   `GUARD_MODEL=gemini-3.5-flash-lite,gemini-3.1-flash-lite` (Leak Guard, motive judge, fallback lines, summaries).
   `client.py` tries each model in order; on 429/503/5xx/timeouts it retries once after 1.5 s then moves down the
   ladder; on 400 INVALID_ARGUMENT it retries the same model once WITHOUT `thinking_config` (some models reject
   `thinking_budget`), then moves on.
4. **Structured output instead of forced tool use.** Every Gemini call uses
   `GenerateContentConfig(system_instruction=<str>, response_mime_type="application/json", response_json_schema=<JSON
   schema dict>, max_output_tokens=…, thinking_config=ThinkingConfig(thinking_level="low"))` and parses
   `response.text` with `json.loads`; the Director validates every field exactly as PLAN §7.3 describes. The "tool"
   JSON schemas in `agents/tools.py` are the same objects (name, description, input_schema); `input_schema` is what is
   passed as `response_json_schema`. Do not use function calling. `max_output_tokens`: 1200 character/guard/judge,
   8000 Watson, 60000 Author. Async client: `genai.Client(api_key=…).aio.models.generate_content(model=…, contents=…, config=…)`;
   `contents` is a list of `types.Content(role="user"|"model", parts=[types.Part(text=…)])` — the suspect's stored
   conversation maps assistant→"model". No explicit context caching (the stable block is below the cache minimum);
   keep Block A byte-stable anyway so Gemini's implicit caching can hit.
5. **Brand.** The UI is titled "Murder Mystery Mayhem" (owner's mockups); package/repo name stays `alibi`.
6. **Frontend stack as installed:** React 19, react-router-dom 7, Vite 8, TypeScript 6, Tailwind 4 via
   `@tailwindcss/vite` (no tailwind.config.js; use `@import "tailwindcss";` in CSS), Zustand 5, @xyflow/react 12,
   howler, @mediapipe/tasks-vision, vitest. Path alias `@/` → `src/`.
7. **Portraits** are procedural pixel art rendered client-side from `portrait_prompt` (public, cosmetic). PublicSuspect
   therefore carries `portrait_prompt`; `portrait_url` stays (null unless a generated image exists).
8. **Confrontation interjection** is a separate endpoint (`POST /confront/interject`) consumed between rounds.
9. **Database**: SQLite file `backend/alibi.db`; `Base.metadata.create_all` at startup. Tables per PLAN §5.
10. **Clock** starts at 00:15 (night of the murder); dawn (05:00+) is cosmetic only.
11. **Extra cases** live in `backend/app/cases/*.json`; every file there is loaded at startup and validated with the
    same rules as `scripts/validate_case.py`; a case that fails validation is skipped with a logged error.
12. **UI wording**: the status pill says "Suspects: Live Gemini" or "Suspects: Scripted"; the settings modal asks for a
    Gemini API key; `POST /settings/api-key` writes `GEMINI_API_KEY`.

## 1. Shared state shapes (plain dicts; JSON-serialisable; these ARE the snapshot)

```python
SuspectState = {
  "suspect_id": str, "stress": int,
  "unlocked_secret_ids": list[str], "revealed_secret_ids": list[str],
  "heard_log": list[{"from": str, "text": str, "turn": int, "channel": "private"|"confrontation"}],
  "outbox": list[{"to": str, "text": str, "queued_turn": int}],
  "flatter_count": int, "threaten_count": int, "silenced_until": int|None,
  "emotion": str, "tell": str, "last_seen_location": str,
  "conversation": list[{"role": "user"|"assistant", "content": str}],   # this suspect's own transcript only
  "last_internal_reasoning": str, "last_honesty": str, "last_accuses": str|None,
  "last_system_blocks": list[str],          # exact system text of the last performer call (Judge Panel Context Boxes)
}
EvidenceState = {"state": "hidden"|"known"|"examined"|"destroyed", "examined_turn": int|None}
World = {
  "game": {"turn": int, "clock_minutes": int, "status": "briefing"|"investigating"|"closed", "difficulty": str,
           "searched_locations": list[str], "fired_framing_actions": list[str], "offscreen_ticks": int,
           "tactics_used": dict[str,int], "composure_samples": list[float]},
  "suspects": dict[str, SuspectState],
  "evidence": dict[str, EvidenceState],
}
```

`engine/snapshot.py`: `take(world) -> dict` (deep copy) and `restore(snapshot) -> World`.

## 2. engine/ (deterministic; never imports google.genai or app.agents)

- `conditions.py` — `class ConditionError(ValueError)`; `evaluate(expr: str, ctx: dict) -> bool` where
  `ctx = {"examined": set, "known": set, "revealed": set, "stress": int, "flatter_count": int, "threaten_count": int,
  "turn": int, "searched": set, "clock_minutes": int}`; `context_for(case, world, suspect_id) -> ctx`.
  Grammar per PLAN §6 (`and` binds tighter than `or`; `not ` prefix; no parentheses; unknown token raises).
- `stress.py` — `compute_delta(model_delta, *, tactic, evidence_points_to_self, sensitivity, composure, difficulty) -> int`
  (PLAN §8.2); `apply_decay(world, addressed_ids)`; `stress_pct(case_suspect, state) -> int` (0–100 of t3, capped);
  `recompute_unlocks(case, world, suspect_id) -> list[str]` (monotonic; writes state); `is_unlockable_tier(...)`;
  `near_cracks(case, world) -> list[{suspect_id, secret_id, stress, threshold}]` (locked tier within 2 of stress or
  special_unlock missing while stress suffices).
- `social.py` — `queue_wants_to_tell(case, world, from_id, wants: list, turn)`; `should_tick(turn, difficulty, every) -> bool`;
  `run_offscreen_tick(case, world, rng) -> list[{from,to,text,turn,channel}]` (queues rumor_seeds on the first
  tick; delivers per PLAN §8.7; drops the rest); `add_heard(world, to_id, from_id, text, turn, channel)`.
- `world.py` — `initial_world(case, difficulty) -> World`; `search(case, world, location_id) -> list[str]` (newly
  examined evidence ids; clock +10; records searched); `advance_clock(world, minutes)`; `clock_str(minutes) -> "HH:MM"`;
  `evaluate_framing_actions(case, world, rng) -> list[{suspect_id, action_id, ticker, evidence}]`;
  `public_evidence(case, world) -> list[PublicEvidence]`; `evidence_text_for_present(case, world, eid) -> str`;
  `known_or_examined_ids(world) -> set`.
- `scoring.py` — `score(case, suspect_id, method_evidence_ids, motive_points) -> {murderer, method, motive, total}`;
  `rank(total) -> "Inspector"|"Detective"|"Rookie"`; `confidence_badge(conf) -> "bold call"|"hedged"|None`.
- `debrief.py` — `build(case, world, turn_rows: list[dict], guard_rows: list[dict], accusation: dict, cast_public) -> Debrief`.
- `director.py` — the orchestrator. It receives injected async callables so it never imports agents:
  ```python
  class Director:
      def __init__(self, case, world, *, performer, guard, rng, difficulty, offscreen_every, fallback_lines): ...
      async def player_turn(self, req: dict) -> TurnOutcome      # type ask|tactic|present
      async def confront(self, req: dict, on_line=None, get_interject=None) -> TurnOutcome  # lines streamed via on_line
      def search(self, location_id) -> TurnOutcome
      async def accuse(self, req, motive_points) -> TurnOutcome
  TurnOutcome = {"public_turns": list[PublicTurn], "private_turns": list[dict],  # rows for the turns table
                 "guard_events": list[dict], "world_events": list[dict], "tickers": list[str], "offscreen": dict|None}
  ```
  Validation of performer output per PLAN §7.3 lives here (`validate_output(raw, ctx) -> (clean, events)`), as do
  shutdown rules (§8.4), silence handling, stress application, decay, unlock recompute, heard_log/outbox updates,
  framing actions, and the clock. `player_signal` handling per §8.5. The performer is called at most once per
  suspect per turn (retries for leaks excepted).

## 3. agents/ (the only package that imports google.genai)

Performer protocol (both implementations return the raw `respond_as_character` dict, un-validated):
```python
PerformContext = {
  "case": {"title": str, "setting": str},
  "suspect": <case suspect dict>,          # ONLY this suspect
  "state": SuspectState,                   # ONLY this suspect's state
  "unlocked": list[str], "locked": list[str],
  "user_message": str,                     # already formatted per PLAN §7.2 ("Detective: …", "The detective shows you: …")
  "turn_type": "ask"|"tactic"|"present"|"confront"|"interject", "tactic": str|None,
  "evidence": {"id","name","text","points_to_self": bool}|None,
  "player_signal": dict|None, "confrontation_with": {"id","name"}|None,
  "retry_ids": list[str],                  # non-empty on leak retry
  "difficulty": str, "suspect_ids": list[str], "cast_names": dict[str,str],   # ids/names of everyone (public info)
}
class Performer(Protocol):
    mode: str                                            # "gemini" | "scripted"
    async def perform(self, ctx: PerformContext) -> dict  # raw tool output; also sets ctx["system_blocks"] = [str,...]
```
- `client.py` — `async def call_tool(model, system_text, messages, tool, *, max_tokens=1200, temperature=0.9) -> dict`
  (Gemini structured JSON output per §0.2 incl. the model ladder and retries; raises `InvalidOutput` on bad JSON /
  missing required keys and `LLMUnavailable` when every model fails; logs model/latency/tokens);
  `credential_available() -> bool`; `resolve_mode(settings) -> "gemini"|"scripted"`.
- `tools.py` — the JSON tool schemas: `RESPOND_AS_CHARACTER` (PLAN §7.3 verbatim), `LEAK_CHECK`, `NOTEBOOK_UPDATE`,
  `GRADE_MOTIVE`, `FALLBACK_LINES`, `SUMMARIZE`, `WRITE_CASE` (case schema), `SOLVE_CASE`, `ALTERNATIVE_CASE`, `GRADE_ALTERNATIVE`.
- `suspect.py` — `build_system_blocks(ctx) -> list[str]` ([Block A, Block B] texts) and `GeminiPerformer`.
- `scripted.py` — `ScriptedPerformer` (see §5 below).
- `performer.py` — `get_performer(settings) -> Performer`.
- `leak_guard.py` — `async def check(spoken, locked_secrets: list[{id,text,key_phrases}], mode) -> {"leaked": [...], "reason": str}`
  (always runs the `key_phrases` regex check; in gemini mode also the GUARD_MODEL call; union of both).
- `watson.py` — `async def update(visible: dict, mode) -> NotebookEntry` (scripted mode: rule-based extraction; gemini mode falls back to the rule-based notebook on LLMUnavailable).
- `judge.py` — `async def grade_motive(motive_text, solution_motive, mode) -> {"points": 0|10|20, "note": str}`;
  `async def fallback_lines(case, mode) -> dict[sid, line]`; `async def summarize(messages, mode) -> str`.
- `author.py` / `checker.py` — M6 (gemini only); `checker.static_check(case) -> list[str]` is pure code (port of
  scripts/validate_case.py) and is used by case loading in every mode.

## 4. app layer

- `config.py` — pydantic-settings `Settings` reading `backend/.env`: GEMINI_API_KEY, SUSPECT_MODEL, AUTHOR_MODEL,
  GUARD_MODEL, DATABASE_URL, DEBUG_PANEL, OFFSCREEN_EVERY, LLM_MODE, FAKE_LLM, RNG_SEED, CORS_ORIGINS.
- `models.py` — PLAN §5 tables (SQLAlchemy 2 async, JSON columns).
- `schemas.py` — Pydantic models for every request/response in §6 below.
- `routers/` — `cases.py`, `games.py`, `debug.py`, `ws.py`, `settings.py`, `tts.py`.
- `services/game_service.py` — loads case + world from DB, runs the Director, persists turns/snapshots BEFORE
  responding, broadcasts WS events. One asyncio.Lock per game id.
- `main.py` — FastAPI app, CORS, routers, startup (create_all, load cases from `app/cases/*.json` into `cases` table
  if missing), `/api/health`.

## 5. Scripted performer rules (`agents/scripted.py`)

Deterministic (seeded by game id + turn) and isolation-safe: it sees only its own PerformContext. Algorithm:
1. If `retry_ids` non-empty → return a deflection (never the secret).
2. Topic detection: score each of this suspect's secrets against the detective's message using word overlap with
   the secret `text`, `cover_story`, and the literal words inside `key_phrases`, plus a small synonym table
   (garden/terrace/outside; telephone/ring/call; cigars/cigar case/room; sacked/dismissed/reference; gloves/study/
   corridor; poison/cyanide/decanter/brandy; embezzle/money/accounts/ledger/Manchester; affair/lover/France; …).
   Pick the best secret if score ≥ 2 words, else none.
3. If the topic secret is **unlocked** and not yet revealed → reveal: `spoken` = first-person rendering of the
   secret `text` (pronoun transform She/He→I, her/his→my, herself/himself→myself, "<Name> …" of self→"I …") wrapped
   in a persona-flavoured opener chosen from the speech_quirk (e.g. Ada: "…Very well, sir."); `honesty=truthful`,
   `reveals=[id]`, `stress_delta=1`, emotion `sad|afraid|angry` by personality; `wants_to_tell` to the most trusted
   relationship if type in {lover, ally, trusts} ("The detective asked me about <topic>. Be careful.").
   If already revealed → restate it briefly (truthful, no reveals).
4. If the topic secret is **locked** → if it has a `cover_story` say it in first person (`honesty=lie`), else a
   `deflection` (`honesty=evasive`). Tier-3 topics add the angry/afraid emotion and `stress_delta=2`.
5. No topic → find the `knowledge` item with the best overlap that does NOT match any locked secret's `key_phrases`
   regex and does not contain a locked secret's distinctive words; answer with it in first person (`truthful`).
   Else a deflection; if a deflection mentions another suspect's name, set `accuses` to that id.
6. `present` turns: if `evidence.points_to_self` → nervous/afraid, `stress_delta=2`, spoken = cover story of the
   most related locked secret if any else a deflection; if it points elsewhere → calm remark that redirects
   (`accuses` = a suspect named in the deflection if any).
7. Tactics: flatter → warmer, more forthcoming (treat as +1 topic score for tier-1/2 secrets); threaten → angry,
   formal, `stress_delta=2`, deflect; bluff → "treat it as a bluff" line unless the bluff's topic secret is unlocked;
   silence → a nervous filler that leans toward the highest-tier unlocked, unrevealed secret if any.
8. Confrontations: address the other suspect by name; if relationship type is lover/ally/trusts → align ("We were
   both … as we said"); if dislikes/leverage/threatens → point suspicion at them (`accuses` = other id) using a
   deflection that names them or a generic line; the murderer prefers redirecting to the other party.
9. Always: run the regex leak check on the final `spoken` against locked secrets; on a hit replace with a deflection.
   `internal_reasoning` = one honest sentence about what is being hidden ("I must not let them near the garden;
   I'll blame Pell."). `tell` from `tells` by emotion (nervous/angry/cracking) else "".

## 6. API (PLAN §9 plus these additions; all under /api)

- `GET /health` → `{ok: true, llm_mode: "gemini"|"scripted", debug_panel: bool, models: {suspect, author, guard}, cases: int}`
- `POST /settings/api-key {api_key}` → `{llm_mode}` (a Gemini key; writes GEMINI_API_KEY into backend/.env, updates process env; local dev convenience)
- `GET /cases` → `[{id, title, setting, generated, n_suspects, preset}]` (`preset` ∈ manor|liner|startup|dorm|room|other, derived from setting keywords)
- `GET /cases/{id}/export` → the case JSON with `solution`, `timeline_truth`, secrets etc. included (it is a share seed)
- `POST /cases/import` `{case: {...}}` → `{case_id}` after static_check
- `POST /cases/generate` (gemini only) → 202 `{job_id}`; `GET /cases/jobs/{job_id}` → `{status, progress: [str], case_id?, checker_report?}`
- `GET /games` → `[{game_id, case_id, case_title, setting, difficulty, status, turn, created_at, correct: bool|null, rank: str|null}]`
- `POST /games`, `GET /games/{id}`, `POST /games/{id}/turn`, `POST /games/{id}/confront`, `POST /games/{id}/confront/interject {text}`,
  `POST /games/{id}/search`, `POST /games/{id}/accuse`, `GET /games/{id}/debrief`, `POST /games/{id}/rewind {turn}`,
  `POST /games/{id}/retry` → `{game_id}` (new game, same case/difficulty), `GET /games/{id}/debug`, `WS /ws/games/{id}`.

Shapes (superset of PLAN §9):
```
PublicSuspect  = {id, name, role, public_description, portrait_prompt, portrait_url: null|str, stress_pct, emotion, tell,
                  silenced: bool, last_seen_location, voice: {webspeech_index?, base_pitch?}|null}
PublicEvidence = {id, name, location, state, description, examined_detail?: str}
PublicLocation = {id, name, description, searched: bool}
PublicTurn     = {turn, seq, type, actor, target, detective_text?, tactic?, evidence_id?, spoken?, tell?, emotion?,
                  stress_pct?, clock, other?: str}          # other = the second suspect in a confrontation line
GameState      = {game_id, status, turn, clock, case: {id, title, setting, briefing, victim: {name, description, cause_of_death_public},
                  timeline_public}, difficulty, llm_mode, cast: PublicSuspect[], evidence: PublicEvidence[],
                  locations: PublicLocation[], turns: PublicTurn[], notebook: NotebookEntry|null, ticker: string[],
                  accessibility: {}, can_rewind_to: int[]}
Briefing       = {game_id, title, setting, briefing, victim, timeline_public, cast, evidence, locations}
NotebookEntry  = PLAN §7.5 + {turn}
Debrief        = PLAN §9 Debrief + {game_id, case_title, cast: PublicSuspect[], turns: PublicTurn[],
                  truth: {murderer, murderer_name, method, motive, timeline_truth, red_herrings, cause_of_death_truth}}
DebugState     = {llm_mode, models: {suspect, author, guard}, turn, clock, suspects: {sid: {name, stress, thresholds, unlocked, locked, revealed,
                  secrets: [{id,tier,text,status}], heard_log, outbox, emotion, last_honesty, last_internal_reasoning,
                  last_accuses, system_blocks: [str], silenced_until}}, evidence: {eid: state}, guard_events: [...],
                  world_events: [...], fired_framing_actions: [...], cross_contamination: [{suspect_id, found: str}]}
```
WS events: `turn_result`, `confront_line`, `confront_done {turn}`, `ticker {text}`, `clock {clock}`, `world_event {text, evidence?}`,
`notebook_updated {NotebookEntry}`, `guard_event {…}` (only when DEBUG_PANEL=1), `pending {suspect_id}`.

Forbidden keys in any non-debug response are enforced by `tests/test_api.py` exactly as PLAN §9 lists them.

## 7. Frontend contracts

- `src/api/types.ts` mirrors §6 by hand (kept in sync; `make types` regenerates `types.gen.ts` from /openapi.json as a check).
- `src/api/client.ts`: one function per endpoint, all returning typed promises; base URL from `VITE_API_URL` (default
  `http://localhost:8000`); errors throw `ApiError {status, message}`.
- `src/api/ws.ts`: `connectGameSocket(gameId, onEvent)` with auto-reconnect.
- `src/store/game.ts` (Zustand): `{ game: GameState|null, loading, pending: {suspectId}|null, selection: {primary, secondary},
  confrontation: {active, lines: PublicTurn[], a, b}|null, toasts, actions: loadGame(id), ask(text), present(evidenceId),
  tactic(kind, text?), confront(topic, rounds, justWatch), interject(text), search(locationId), accuse(payload), rewind(turn),
  select(id, secondary?), applyEvent(evt) }`.
- `src/store/ui.ts`: `{ a11y: {voice, screenReader, lowSensory, dyslexia, plainLanguage}, judgeOpen, ttsProvider, actionTab }`,
  persisted to localStorage (try/catch).
- `src/store/sensors.ts`: `{ consent, enabled, composure, gaze, voiceStress, lastSampleAt, start(), stop(), signal() }`.
- `src/sensors/index.ts` exports `startFace(video, onSample)`, `stopFace()`, `startVoiceStress(stream, onSample)`; foundation
  ships stubs, the sensors lane fills them in.
- `src/voice/index.ts` exports `speak(suspect: PublicSuspect, text: string, stressPct: number)`, `stopSpeaking()`,
  `useSTT(onFinal: (t: string) => void) → {listening, start, stop, supported}`.
- `src/audio/heartbeat.ts` exports `setHeartbeat(stressPct: number, enabled: boolean)`.
- `src/components/portrait/PixelPortrait.tsx` props `{suspect: {id, name, portrait_prompt}, emotion?, size?, className?}`.
- `src/components/sensors/ComposureMeter.tsx` (no props) and `ConsentGate.tsx` `{checked, onChange}`.
- CSS classes from the design system are documented at the top of `src/styles/theme.css` (e.g. `.parchment`,
  `.lacquer`, `.placard`, `.btn-red`, `.btn-black`, `.section-title`, `.sticky`, `.marquee`, `.pressure-bar`).
