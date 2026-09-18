/**
 * Hand-written mirror of docs/INTERFACES.md §6 (API shapes) and PLAN.md §9.
 * Keep in sync with the backend; `make types` regenerates types.gen.ts from /openapi.json as a check.
 *
 * Nothing in here may carry a secret: no internal_reasoning / honesty / reveals outside the Debrief and DebugState.
 */

// ---------------------------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------------------------

export type Difficulty = 'rookie' | 'detective' | 'inspector'
export type LlmMode = 'gemini' | 'scripted'
export type GameStatus = 'briefing' | 'investigating' | 'closed'
export type Emotion = 'neutral' | 'nervous' | 'angry' | 'smug' | 'sad' | 'afraid'
export type Honesty = 'truthful' | 'evasive' | 'lie'
export type Tactic = 'bluff' | 'flatter' | 'threaten' | 'silence'
export type TurnType = 'ask' | 'tactic' | 'present' | 'confront' | 'search' | 'accuse' | 'offscreen' | 'world'
export type EvidenceStateKind = 'hidden' | 'known' | 'examined' | 'destroyed'
export type Composure = 'nervous' | 'neutral' | 'confident'
export type Gaze = 'suspect' | 'evidence' | 'notebook' | 'away'
export type CasePreset = 'manor' | 'liner' | 'startup' | 'dorm' | 'room' | 'other'
export type Rank = 'Inspector' | 'Detective' | 'Rookie'
export type ConfidenceBadge = 'bold call' | 'hedged' | null
export type MessageChannel = 'private' | 'confrontation'

export const EMOTIONS: readonly Emotion[] = ['neutral', 'nervous', 'angry', 'smug', 'sad', 'afraid']
export const DIFFICULTIES: readonly Difficulty[] = ['rookie', 'detective', 'inspector']
export const TACTICS: readonly Tactic[] = ['bluff', 'flatter', 'threaten', 'silence']

// ---------------------------------------------------------------------------------------------
// Health / settings / cases
// ---------------------------------------------------------------------------------------------

export interface ModelLadder {
  suspect: string
  author: string
  guard: string
}

export interface Health {
  ok: boolean
  llm_mode: LlmMode
  debug_panel: boolean
  models: ModelLadder
  cases: number
}

export interface ApiKeyResponse {
  llm_mode: LlmMode
}

export interface CaseSummary {
  id: string
  title: string
  setting: string
  generated: boolean
  n_suspects: number
  preset: CasePreset
}

export interface GenerateCaseRequest {
  setting: string
  n_suspects: number
  difficulty: Difficulty
}

export interface GenerateCaseResponse {
  job_id: string
}

export type CaseJobStatus = 'queued' | 'running' | 'done' | 'failed'

export interface CaseJob {
  status: CaseJobStatus | string
  progress: string[]
  case_id?: string | null
  checker_report?: unknown
  error?: string | null
}

export interface ImportCaseResponse {
  case_id: string
}

/** The full case JSON (share seed). Structure per PLAN.md §6; only used opaquely on the client. */
export type CaseExport = Record<string, unknown> & { id: string; title: string; setting: string }

// ---------------------------------------------------------------------------------------------
// Games
// ---------------------------------------------------------------------------------------------

/** Free-form accessibility JSON stored on the game (PLAN §5). The client sends these snake_case flags. */
export interface AccessibilityPayload {
  voice: boolean
  screen_reader: boolean
  low_sensory: boolean
  dyslexia: boolean
  plain_language: boolean
  camera: boolean
  [extra: string]: unknown
}

export interface GameSummary {
  game_id: string
  case_id: string
  case_title: string
  setting: string
  difficulty: Difficulty
  status: GameStatus
  turn: number
  created_at: string
  correct: boolean | null
  rank: Rank | string | null
}

export interface CreateGameRequest {
  case_id: string
  difficulty: Difficulty
  accessibility: Partial<AccessibilityPayload> & { [extra: string]: unknown }
}

export interface CreateGameResponse {
  game_id: string
  briefing: BriefingData
}

export interface SuspectVoice {
  webspeech_index?: number
  base_pitch?: number
  elevenlabs_voice_id?: string
}

export interface PublicSuspect {
  id: string
  name: string
  role: string
  public_description: string
  portrait_prompt: string
  portrait_url: string | null
  stress_pct: number
  emotion: Emotion
  tell: string
  silenced: boolean
  last_seen_location: string
  voice: SuspectVoice | null
}

export interface PublicEvidence {
  id: string
  name: string
  location: string
  state: EvidenceStateKind
  description: string
  examined_detail?: string
}

export interface PublicLocation {
  id: string
  name: string
  description: string
  searched: boolean
}

export interface PublicTurn {
  turn: number
  seq: number
  type: TurnType
  actor: 'detective' | 'director' | string
  target: string | null
  detective_text?: string
  tactic?: Tactic
  evidence_id?: string
  spoken?: string
  tell?: string
  emotion?: Emotion
  stress_pct?: number
  clock: string
  /** The second suspect in a confrontation line (the listener). */
  other?: string
}

export interface TimelineEntry {
  time: string
  event: string
}

export interface PublicVictim {
  name: string
  description: string
  cause_of_death_public: string
}

export interface GameCase {
  id: string
  title: string
  setting: string
  briefing: string
  victim: PublicVictim
  timeline_public: TimelineEntry[]
}

export interface GameState {
  game_id: string
  status: GameStatus
  turn: number
  clock: string
  case: GameCase
  difficulty: Difficulty
  llm_mode: LlmMode
  cast: PublicSuspect[]
  evidence: PublicEvidence[]
  locations: PublicLocation[]
  turns: PublicTurn[]
  notebook: NotebookEntry | null
  ticker: string[]
  accessibility: Record<string, unknown>
  can_rewind_to: number[]
}

export interface BriefingData {
  game_id: string
  title: string
  setting: string
  briefing: string
  victim: PublicVictim
  timeline_public: TimelineEntry[]
  cast: PublicSuspect[]
  evidence: PublicEvidence[]
  locations: PublicLocation[]
}

// ---------------------------------------------------------------------------------------------
// Player actions
// ---------------------------------------------------------------------------------------------

export interface PlayerSignal {
  composure?: Composure
  gaze?: Gaze
  voice_stress?: number
}

export interface AskTurnRequest {
  type: 'ask'
  suspect_id: string
  text: string
  player_signal?: PlayerSignal
}

export interface TacticTurnRequest {
  type: 'tactic'
  suspect_id: string
  tactic: Tactic
  text?: string
  player_signal?: PlayerSignal
}

export interface PresentTurnRequest {
  type: 'present'
  suspect_id: string
  evidence_id: string
  player_signal?: PlayerSignal
}

export type TurnRequest = AskTurnRequest | TacticTurnRequest | PresentTurnRequest

export interface ConfrontRequest {
  a: string
  b: string
  topic: string
  rounds?: number
  interject?: string
  player_signal?: PlayerSignal
}

export interface ConfrontResponse {
  lines: PublicTurn[]
}

export interface InterjectRequest {
  text: string
}

export interface InterjectResponse {
  ok?: boolean
  [key: string]: unknown
}

export interface SearchRequest {
  location_id: string
}

export interface SearchResponse {
  evidence: PublicEvidence[]
  clock: string
}

export interface AccuseRequest {
  suspect_id: string
  method_evidence_ids: string[]
  motive_text: string
  confidence: number
}

export interface RewindRequest {
  turn: number
}

export interface RetryResponse {
  game_id: string
}

// ---------------------------------------------------------------------------------------------
// Watson notebook (PLAN §7.5 + turn)
// ---------------------------------------------------------------------------------------------

export interface NotebookClaim {
  quote: string
  where: string
  from: string
  to: string
}

export interface NotebookSuspect {
  id: string
  claims: NotebookClaim[]
  notes: string[]
}

export interface NotebookContradiction {
  a: { suspect: string; quote: string }
  b: { suspect_or_evidence: string; quote: string }
  note: string
}

export interface NotebookEntry {
  turn: number
  per_suspect: NotebookSuspect[]
  contradictions: NotebookContradiction[]
  suggested_next: string[]
}

// ---------------------------------------------------------------------------------------------
// Debrief (only after the game is closed; the one place internal_reasoning/honesty/reveals may appear)
// ---------------------------------------------------------------------------------------------

export interface DebriefScore {
  murderer: number
  method: number
  motive: number
  total: number
}

export interface DebriefTruth {
  murderer: string
  murderer_name: string
  method: string
  motive: string
  timeline_truth: TimelineEntry[]
  red_herrings: string[]
  cause_of_death_truth: string
}

export interface GuardEvent {
  kind: 'reveals_stripped' | 'leak_regenerated' | 'leak_fallback' | 'invalid_output' | 'provider_fallback' | string
  turn?: number
  suspect_id?: string
  detail?: unknown
}

export interface ReelNode {
  turn: number
  seq: number
  suspect_id: string
  detective_text: string
  spoken: string
  internal_reasoning: string
  honesty: Honesty
  stress_before: number
  stress_after: number
  reveals: string[]
  guard_events: GuardEvent[]
}

export interface RumorEdge {
  from: string
  to: string
  text: string
  turn: number
  channel: MessageChannel | string
}

export interface DebriefMissed {
  evidence_never_examined: string[]
  secrets_never_revealed: { suspect_id: string; text: string }[]
  near_cracks: { suspect_id: string; turn: number; stress: number; threshold: number; secret_id: string }[]
  messages_never_learned: { from: string; to: string; text: string }[]
}

export interface DebriefStats {
  turns: number
  clock: string
  evidence_pct: number
  tactics_used: Record<string, number>
  composure_avg?: number | null
}

export interface Debrief {
  game_id: string
  case_title: string
  correct: boolean
  score: DebriefScore
  rank: Rank | string
  confidence_badge: ConfidenceBadge | string
  truth: DebriefTruth
  reel: ReelNode[]
  rumor_map: RumorEdge[]
  missed: DebriefMissed
  stats: DebriefStats
  cast: PublicSuspect[]
  turns: PublicTurn[]
}

// ---------------------------------------------------------------------------------------------
// Debug / Judge panel (GET /games/:id/debug — 404 unless DEBUG_PANEL=1)
// ---------------------------------------------------------------------------------------------

export type SecretStatus = 'locked' | 'unlocked' | 'revealed'

export interface DebugSecret {
  id: string
  tier: 1 | 2 | 3
  text: string
  status: SecretStatus
}

export interface HeardEntry {
  from: string
  text: string
  turn: number
  channel: MessageChannel | string
}

export interface OutboxEntry {
  to: string
  text: string
  queued_turn: number
}

export interface DebugSuspect {
  name: string
  stress: number
  thresholds: [number, number, number] | number[]
  unlocked: string[]
  locked: string[]
  revealed: string[]
  secrets: DebugSecret[]
  heard_log: HeardEntry[]
  outbox: OutboxEntry[]
  emotion: Emotion
  last_honesty: Honesty | string
  last_internal_reasoning: string
  last_accuses: string | null
  system_blocks: string[]
  silenced_until: number | null
}

export interface DebugState {
  llm_mode: LlmMode
  models: ModelLadder
  turn: number
  clock: string
  suspects: Record<string, DebugSuspect>
  evidence: Record<string, EvidenceStateKind>
  guard_events: GuardEvent[]
  world_events: unknown[]
  fired_framing_actions: string[]
  cross_contamination: { suspect_id: string; found: string }[]
}

// ---------------------------------------------------------------------------------------------
// WebSocket events (WS /ws/games/:id) — discriminated union on `type`
// ---------------------------------------------------------------------------------------------

export interface WsTurnResult {
  type: 'turn_result'
  turn: PublicTurn
}
export interface WsConfrontLine {
  type: 'confront_line'
  turn: PublicTurn
}
export interface WsConfrontDone {
  type: 'confront_done'
  turn: number
}
export interface WsTicker {
  type: 'ticker'
  text: string
}
export interface WsClock {
  type: 'clock'
  clock: string
}
export interface WsWorldEvent {
  type: 'world_event'
  text: string
  evidence?: PublicEvidence
}
export interface WsNotebookUpdated {
  type: 'notebook_updated'
  notebook: NotebookEntry
}
export interface WsGuardEvent {
  type: 'guard_event'
  event: GuardEvent
}
export interface WsPending {
  type: 'pending'
  suspect_id: string
}
export interface WsUnknown {
  type: 'unknown'
  raw: unknown
}

export type WsEvent =
  | WsTurnResult
  | WsConfrontLine
  | WsConfrontDone
  | WsTicker
  | WsClock
  | WsWorldEvent
  | WsNotebookUpdated
  | WsGuardEvent
  | WsPending
  | WsUnknown

export type WsEventType = WsEvent['type']

/** Error body shape: FastAPI `{detail}` or PLAN §9 `{error}`. */
export interface ApiErrorBody {
  error?: string
  detail?: string | { msg?: string; loc?: unknown[] }[] | unknown
}
