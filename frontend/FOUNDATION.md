# Frontend foundation — how to build on it

For the **Investigation**, **Debrief + Judge + Archive** and **Sensors + Voice** lanes. Everything described here
exists, compiles (`npm run typecheck && npm run build`) and is tested (`npm test`). Contracts come from
`docs/INTERFACES.md` §7; visuals from `docs/DESIGN.md`.

```
src/
  api/      types.ts (all shapes)  client.ts (one fn per endpoint)  ws.ts (connectGameSocket)
  store/    game.ts  ui.ts  sensors.ts                       (zustand 5)
  lib/      pixelPortrait.ts clock.ts text.ts presets.ts evidenceKind.ts motion.ts storage.ts cn.ts
  styles/   index.css (@import "tailwindcss" + theme.css)  theme.css (the design system — class index at the top)
  components/common/   Button Modal Placard Panel SectionTitle Sticky Marquee RoomBackdrop SceneThumb
                       Toast(er) TypewriterProgress KeyCap ClockFace ApiKeyModal EvidenceIcon ErrorNotice
  components/portrait/ PixelPortrait
  components/sensors/  ComposureMeter ConsentGate        ← placeholders, sensors lane replaces
  components/judge/    JudgePanel                        ← placeholder, judge lane replaces
  sensors/index.ts  voice/index.ts  audio/heartbeat.ts   ← placeholders (same exports), later lanes replace
  screens/  NewCase Briefing  |  Investigation Debrief Archive ← placeholders (keep the default export)
  routes.tsx  App.tsx  main.tsx
```

Routes: `/` NewCase · `/game/:id/briefing` Briefing · `/game/:id` Investigation · `/game/:id/debrief` Debrief ·
`/archive` Archive. `App` renders the room backdrop, `<Outlet/>`, the `Toaster` and the `aria-live` region.
Replacement screens must keep `export default`.

## 1. API client (`@/api/client`)

```ts
import { api, ApiError, isApiError, errorMessage, API_BASE } from '@/api/client'

const game = await api.getGame(id)                              // GameState
const turn = await api.postTurn(id, { type: 'ask', suspect_id: 'pell', text: '…', player_signal })
const { lines } = await api.postConfront(id, { a: 'pell', b: 'ada', topic: '…', rounds: 3 })
await api.postInterject(id, 'And the gloves, Mr Pell?')
const { evidence, clock } = await api.postSearch(id, 'billiard_room')
const debrief = await api.postAccuse(id, { suspect_id, method_evidence_ids, motive_text, confidence })
const dbg = await api.getDebugOrNull(id)                        // null when DEBUG_PANEL is off (404)
```

Every function returns a typed promise and throws `ApiError {status, message, detail}`; `status === 0` means the
backend is unreachable (`e.isNetwork`). `errorMessage(e)` gives a user-facing string. Base URL: `VITE_API_URL`
(default `http://localhost:8000`); REST lives under `${API_BASE}/api`. Timeouts are generous for LLM turns
(120 s turn, 300 s confront).

Types: `@/api/types` — `GameState`, `PublicSuspect`, `PublicEvidence`, `PublicLocation`, `PublicTurn`,
`NotebookEntry`, `Debrief` (+ `ReelNode`, `RumorEdge`, `DebriefMissed`, `DebriefStats`), `DebugState`
(+ `DebugSuspect`, `DebugSecret`, `HeardEntry`), `Health`, `CaseSummary`, `GameSummary`, `PlayerSignal`,
`WsEvent` (discriminated union on `type`), the request bodies, and the enums (`Emotion`, `Tactic`, `Honesty`…).

## 2. WebSocket (`@/api/ws`)

The game store connects automatically in `loadGame(id)`; you rarely need this directly.

```ts
const sock = connectGameSocket(gameId, (evt) => { if (evt.type === 'ticker') … }, { onStatus })
sock.close()
```

Reconnects with backoff (1 s → 15 s). Tries `${API_BASE}/api/ws/games/:id` first, then `/ws/games/:id`.
`normalizeWsMessage(raw)` accepts `{type, data}` (canonical), `{event, payload}` and flattened `{event, …fields}`
envelopes and returns a `WsEvent`:

| `evt.type`         | payload                       |
|--------------------|-------------------------------|
| `turn_result`      | `evt.turn: PublicTurn`        |
| `confront_line`    | `evt.turn: PublicTurn` (`turn.other` = the listener) |
| `confront_done`    | `evt.turn: number`            |
| `ticker`           | `evt.text`                    |
| `clock`            | `evt.clock` ("HH:MM")         |
| `world_event`      | `evt.text`, `evt.evidence?`   |
| `notebook_updated` | `evt.notebook: NotebookEntry` |
| `guard_event`      | `evt.event: GuardEvent`       |
| `pending`          | `evt.suspect_id`              |

Note for the backend: a *flattened* turn envelope must name the event with `event`, because `PublicTurn` has its
own `type` field. `{type: "turn_result", data: {...}}` is the safe canonical form.

## 3. Game store (`@/store/game`)

```ts
import { useGame, selectPrimarySuspect, selectExaminedEvidence, turnsForSuspect, speakerIndex } from '@/store/game'

// in a screen
const loadGame = useGame((s) => s.loadGame)
useEffect(() => { void loadGame(id) }, [id, loadGame])          // fetches GameState + opens the socket

const game      = useGame((s) => s.game)                        // GameState | null
const primary   = useGame(selectPrimarySuspect)                 // PublicSuspect | null
const pending   = useGame((s) => s.pending)                     // {suspectId, kind, since} | null → dim the portrait
const selection = useGame((s) => s.selection)                   // {primary, secondary}
const conf      = useGame((s) => s.confrontation)               // {active, a, b, topic, lines, speaking, done, justWatch}

// actions — never throw; they toast the error and resolve to null
await useGame.getState().ask('Where were you at 11:20?')       // uses selection.primary; or ask(text, suspectId)
await useGame.getState().present('cigar_case')
await useGame.getState().tactic('flatter', 'You strike me as the only sensible person here.')
await useGame.getState().confront('The gloves', 3, /*justWatch*/ false) // uses primary + secondary; or pass {a, b}
await useGame.getState().interject('And the gloves?')          // during a confrontation
useGame.getState().endConfrontation()                          // back to the single-portrait room
await useGame.getState().search('billiard_room')
const debrief = await useGame.getState().accuse({ suspect_id, method_evidence_ids, motive_text, confidence })
await useGame.getState().rewind(9)
const newId  = await useGame.getState().retry()                 // new game, same case
useGame.getState().select('ada')                                // primary
useGame.getState().select('pell', /*secondary*/ true)           // shift-click → confront pair
useGame.getState().addToast({ kind: 'info', text: '…', ttlMs: 5000, action: { label: 'Undo', onClick } })
useGame.getState().announce('Watson updated the notebook.')     // writes the aria-live region
```

- Every player action attaches `useSensors.getState().signal()` (undefined when sensors are off).
- `applyEvent(evt)` merges WS events by `(turn, seq)` — `mergeTurn`, `mergeTurns`, `upsertEvidence`,
  `applyTurnToCast` are exported pure helpers. A `turn_result` for the pending suspect clears `pending`;
  `confront_line` appends to `confrontation.lines` and sets `speaking = line.other`.
- After each action the store re-fetches `GET /games/:id` (`refreshGame`) so decay, evidence, ticker and the
  notebook are consistent even without the socket.
- `guardEvents` collects `guard_event`s (Judge panel); `debrief` caches the Debrief; `socketStatus` for a badge.
- `liveMessage` is what the `aria-live` region in `App` reads out (every line/event).
- Dialogue log rows: `turnsForSuspect(game.turns, id)`; colour a speaker with `` className={`speaker-${speakerIndex(game.cast, id)}`} ``.

## 4. UI store (`@/store/ui`)

```ts
const a11y = useUI((s) => s.a11y)          // {voice, screenReader, lowSensory, dyslexia, plainLanguage}
useUI.getState().toggleA11y('lowSensory')  // persisted (localStorage, try/catch) + mirrored to <html data-low-sensory>
const judgeOpen = useUI((s) => s.judgeOpen); useUI.getState().toggleJudge()
const tab = useUI((s) => s.actionTab);      useUI.getState().setActionTab('present')   // 'ask'|'present'|'tactic'|'confront'|'search'
useUI.getState().ttsProvider                // 'webspeech' | 'elevenlabs' (VITE_TTS_PROVIDER)
```

`<html>` attributes set by the store: `data-dyslexia`, `data-low-sensory`, `data-screen-reader`,
`data-plain-language`, `data-voice`. CSS hooks live in theme.css §10. `A11Y_OPTIONS` drives the four toggles.
`motionDisabled()` from `@/lib/motion` = reduced-motion OR low-sensory — check it before any typing/blink/heartbeat.

## 5. Sensors store (`@/store/sensors`) — for the Sensors + Voice lane

```ts
const { consent, enabled, composure, gaze, voiceStress } = useSensors.getState()
useSensors.getState().setConsent(true)     // the NewCase checkbox (ConsentGate) sets this
await useSensors.getState().start()        // getUserMedia → hidden <video> → startFace(video, onSample)
useSensors.getState().stop()               // stopFace() + stop tracks
useSensors.getState().signal()             // PlayerSignal | undefined  (samples older than 15 s are dropped)
useSensors.getState().setEvidenceTabOpen(true) // gaze "notebook" → "evidence" while the Evidence tab is open
const stopVoice = useSensors.getState().startVoice(micStream)  // during STT; calls startVoiceStress()
```

Implement in `src/sensors/index.ts` (keep the exports): `startFace(video, onSample: (s: FaceSample) => void)`,
`stopFace()`, `startVoiceStress(stream, onSample: (s: VoiceSample) => void): () => void`.
`FaceSample = {composure, gaze, score, blinkRate?, brow?, gazeX?, faceDetected?}` and `VoiceSample = {stress}`
are exported from the store. `composureLabel(c)` → "Calm" / "Neutral" / "Nervous".

Voice (`src/voice/index.ts`): `speak(suspect, text, stressPct)`, `stopSpeaking()`, `useSTT(onFinal)` →
`{listening, start, stop, supported}`. Heartbeat (`src/audio/heartbeat.ts`): `setHeartbeat(stressPct, enabled)`.

## 6. Portraits

```tsx
<PixelPortrait suspect={s} emotion={s.emotion} size={160} dim={pending?.suspectId === s.id} />
```

Sizes 48 / 56 / 96 / 160 / 200 (any number works). Emotions: neutral · nervous · angry · smug · sad · afraid
(unknown → neutral). Blinks unless low-sensory / reduced motion (`still` disables). Alt text is
"Portrait of <name>, looking <emotion>". Canvas with SVG fallback when no 2D context.

Pure helpers in `@/lib/pixelPortrait`: `parseTraits(prompt)`, `buildPortrait({traits, emotion, seed, blink})`,
`portraitFor(prompt, seed, emotion)`, `gridToSvg(grid)`, `gridRuns(grid)`, `renderToCanvas(canvas, grid, scale)`,
`emotionColor(e)`, `toPortraitEmotion(str)`, `describeTraits(t)`. Deterministic per `seed` (use the suspect id).

## 7. Theme classes (full index at the top of `src/styles/theme.css`)

| Need | Use |
|------|-----|
| cream paper card | `.parchment` (+ `--tight`, `--flat`, `--plain`) or `<Panel>` |
| dark gold-framed panel | `.lacquer` (+ `--soft`, `--teal`) or `<Panel variant="lacquer">` |
| brass wall plaque | `.placard` / `<Placard>` |
| sticky note | `.sticky` / `<Sticky>` (Caveat font, push-pin) |
| `—◆— TITLE —◆—` + right subtitle | `<SectionTitle subtitle="…" dark align="left">` |
| buttons | `<Button variant="red|black|ghost" size="sm|md|lg" block loading>` / `.btn .btn-red` |
| pill choice | `.chip` + `.selected` |
| pill switch | `<label class="toggle"><input class="toggle__input" type="checkbox"/><span class="toggle__track"/>…</label>` |
| inputs | `.field` (parchment) / `.field.field--lacquer` (dark); `.checkbox`; `.slider` |
| tabs | `.tab-bar` > `.tab.active` (+ `.tab__hint`); `.tab-bar--parchment` |
| Pressure bar | `<div class="pressure-bar" style="--pct: 40">` (10 segments, green→red) + `.pressure-label` |
| dialogue log | `.dialogue-log` > `.dialogue-log__row.speaker-N` > `__who` / `__text` (`--tell`, `--system`) / `__time` |
| latest spoken line | `.speech-panel` (parchment with notch); floating tell → `.speech-bubble.speech-bubble--left` |
| clock | `<ClockFace time="00:15" dawn />` + `.clock .clock__time` (`.clock--dawn` turns it red) |
| scene picture | `<SceneThumb preset="manor|liner|startup|dorm|room|other" />` |
| evidence icon | `<EvidenceIcon name={e.name} description={e.description} />` |
| loading strip | `<TypewriterProgress active lines={[…]} progress={null} />` |
| key badge | `<KeyCap>`</KeyCap>` |
| toasts | `useGame.getState().addToast(...)` — `<Toaster/>` is already mounted in App |
| modal | `<Modal open onClose title variant="parchment|lacquer" width={720}>` (focus trap, Esc, restore focus) |
| suspect card | `.suspect-card` + `.selected` (gold) / `.secondary` (red) |
| entrance motion | `.fade-in`, `.slide-up` (auto-disabled in low-sensory / reduced motion) |

Colours are CSS variables (`--gold-400`, `--red-600`, `--paper-200`, `--ink`, `--truth`/`--deflect`/`--lie`,
`--emotion-*`, `--speaker-0…4`). Text on parchment is `--ink`; on lacquer `--paper-200`; never pure white.
Layout with Tailwind utilities (`grid`, `gap-4`, `lg:grid-cols-[20fr_55fr_25fr]`…), materials with these classes.

## 8. Other helpers

- `@/lib/clock`: `parseClock`, `formatClock12("23:20") → "11:20 PM"`, `clockPhase`, `isDawn` (≥ 05:00).
- `@/lib/text`: `extractAlibi(public_description)`, `shortName("Dr. Elias Crane") → "Crane"`, `deriveDeathWindow`,
  `deriveCrimeScene`, `sentences`, `truncate`, `numberWord`.
- `@/lib/presets`: `PRESET_TILES`, `casesForPreset`, `presetFromSetting`.
- `@/lib/storage`: `loadJSON` / `saveJSON` (never throw).

## 9. Decisions taken in this lane

- `accessibility` sent with `POST /games` is `{voice, screen_reader, low_sensory, dyslexia, plain_language, camera}`.
- WS envelope: `{type, data}` canonical; `{event, …}` also accepted (see §2). Socket path: `/api/ws/games/:id` then `/ws/games/:id`.
- Camera consent is kept in memory only (not persisted) — it is a per-session decision.
- The "Begin investigation" button navigates to `/game/:id` without a backend call; the first turn moves the game
  from `briefing` to `investigating` server-side.
- Detective interjections are shown locally in `confrontation.lines` with a fractional `seq` (`last + 0.5`) so
  they order between the server's integer-seq lines.
- `Investigation`, `Debrief`, `Archive` are lazy routes; keep them as `export default` components.
