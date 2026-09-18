/**
 * Game store (docs/INTERFACES.md §7). One store per browser tab; `loadGame(id)` swaps the game.
 *
 *  - `game` is the last GameState from the server; `applyEvent` merges WS events into it by (turn, seq).
 *  - `pending` is set while a suspect is answering (portrait dims, nervous tell shows).
 *  - `confrontation` collects streamed `confront_line` events while a confrontation runs.
 *  - Every player action attaches `useSensors.getState().signal()` when sensors are on.
 *  - Errors never throw out of actions: they become an error toast and the action resolves to null.
 */
import { create } from 'zustand'
import { api, errorMessage } from '@/api/client'
import { connectGameSocket, type GameSocket, type SocketStatus } from '@/api/ws'
import type {
  AccuseRequest,
  Debrief,
  GameState,
  GuardEvent,
  PublicEvidence,
  PublicSuspect,
  PublicTurn,
  SearchResponse,
  Tactic,
  TurnRequest,
  WsEvent,
} from '@/api/types'
import { useSensors } from './sensors'

// ---------------------------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------------------------

export type ToastKind = 'info' | 'error' | 'success' | 'ticker' | 'world'

export interface Toast {
  id: string
  kind: ToastKind
  text: string
  /** small caps label above the text, e.g. "Recent events" */
  kicker?: string
  /** auto-dismiss after this many ms (0 = sticky) */
  ttlMs: number
  action?: { label: string; onClick: () => void }
}

export interface PendingState {
  suspectId: string
  kind: 'ask' | 'tactic' | 'present' | 'confront' | 'search' | 'accuse'
  since: number
}

export interface Selection {
  primary: string | null
  secondary: string | null
}

export interface Confrontation {
  active: boolean
  a: string
  b: string
  topic: string
  rounds: number
  justWatch: boolean
  lines: PublicTurn[]
  /** suspect id currently generating a line (from `pending` / the previous line's `other`) */
  speaking: string | null
  done: boolean
  startedAt: number
}

export interface GameStoreState {
  gameId: string | null
  game: GameState | null
  loading: boolean
  error: string | null
  pending: PendingState | null
  selection: Selection
  confrontation: Confrontation | null
  toasts: Toast[]
  socketStatus: SocketStatus
  guardEvents: GuardEvent[]
  debrief: Debrief | null
  /** text for the aria-live region (every dialogue line and event) */
  liveMessage: string

  // lifecycle
  loadGame: (id: string) => Promise<GameState | null>
  refreshGame: () => Promise<GameState | null>
  connect: (id?: string) => void
  disconnect: () => void
  leaveGame: () => void

  // player actions (PLAN §8.1)
  ask: (text: string, suspectId?: string) => Promise<PublicTurn | null>
  present: (evidenceId: string, suspectId?: string) => Promise<PublicTurn | null>
  tactic: (kind: Tactic, text?: string, suspectId?: string) => Promise<PublicTurn | null>
  confront: (topic: string, rounds?: number, justWatch?: boolean, pair?: { a: string; b: string }) => Promise<PublicTurn[] | null>
  interject: (text: string) => Promise<boolean>
  endConfrontation: () => void
  search: (locationId: string) => Promise<SearchResponse | null>
  accuse: (payload: AccuseRequest) => Promise<Debrief | null>
  loadDebrief: (id?: string) => Promise<Debrief | null>
  rewind: (turn: number) => Promise<GameState | null>
  retry: () => Promise<string | null>

  // selection
  select: (id: string, secondary?: boolean) => void
  clearSelection: () => void

  // events / ui
  applyEvent: (evt: WsEvent) => void
  addToast: (toast: Omit<Toast, 'id' | 'ttlMs'> & { ttlMs?: number }) => string
  dismissToast: (id: string) => void
  announce: (text: string) => void
  setError: (message: string | null) => void
}

// ---------------------------------------------------------------------------------------------
// Pure helpers (exported so other lanes and tests can reuse them)
// ---------------------------------------------------------------------------------------------

export function turnKey(t: Pick<PublicTurn, 'turn' | 'seq'>): string {
  return `${t.turn}:${t.seq}`
}

/** Insert or replace a turn by (turn, seq), keeping the list sorted. Returns a new array. */
export function mergeTurn(turns: PublicTurn[], incoming: PublicTurn): PublicTurn[] {
  const key = turnKey(incoming)
  const idx = turns.findIndex((t) => turnKey(t) === key)
  if (idx >= 0) {
    const next = turns.slice()
    next[idx] = { ...turns[idx], ...incoming }
    return next
  }
  const next = [...turns, incoming]
  next.sort((a, b) => a.turn - b.turn || a.seq - b.seq)
  return next
}

export function mergeTurns(turns: PublicTurn[], incoming: PublicTurn[]): PublicTurn[] {
  return incoming.reduce((acc, t) => mergeTurn(acc, t), turns)
}

export function upsertEvidence(list: PublicEvidence[], e: PublicEvidence): PublicEvidence[] {
  const idx = list.findIndex((x) => x.id === e.id)
  if (idx < 0) return [...list, e]
  const next = list.slice()
  next[idx] = { ...list[idx], ...e }
  return next
}

/** Reflect what a suspect's turn tells us (emotion, tell, pressure) on the cast card. */
export function applyTurnToCast(cast: PublicSuspect[], t: PublicTurn): PublicSuspect[] {
  if (!t.actor || t.actor === 'detective' || t.actor === 'director') return cast
  const idx = cast.findIndex((s) => s.id === t.actor)
  if (idx < 0) return cast
  const cur = cast[idx]!
  const patch: Partial<PublicSuspect> = {}
  if (t.emotion) patch.emotion = t.emotion
  if (typeof t.tell === 'string') patch.tell = t.tell
  if (typeof t.stress_pct === 'number') patch.stress_pct = t.stress_pct
  if (!Object.keys(patch).length) return cast
  const next = cast.slice()
  next[idx] = { ...cur, ...patch }
  return next
}

/** Short spoken summary for the aria-live region. */
export function describeTurn(t: PublicTurn, cast: PublicSuspect[]): string {
  const name = cast.find((s) => s.id === t.actor)?.name ?? t.actor
  if (t.actor === 'detective') return t.detective_text ? `You: ${t.detective_text}` : ''
  if (t.actor === 'director') return t.spoken ?? t.detective_text ?? ''
  const parts: string[] = []
  if (t.spoken) parts.push(`${name}: ${t.spoken}`)
  if (t.tell) parts.push(`(${t.tell})`)
  return parts.join(' ')
}

let toastCounter = 0
function nextToastId(): string {
  toastCounter += 1
  return `t${Date.now().toString(36)}${toastCounter}`
}

// ---------------------------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------------------------

let socket: GameSocket | null = null
let socketGameId: string | null = null

const EMPTY_SELECTION: Selection = { primary: null, secondary: null }

export const useGame = create<GameStoreState>()((set, get) => {
  const fail = (e: unknown, fallback: string): null => {
    const message = errorMessage(e, fallback)
    set({ error: message, pending: null })
    get().addToast({ kind: 'error', text: message, ttlMs: 8000 })
    return null
  }

  const targetId = (explicit?: string): string | null => explicit ?? get().selection.primary

  const mergeTurnIntoGame = (t: PublicTurn) => {
    const game = get().game
    if (!game) return
    set({
      game: {
        ...game,
        turns: mergeTurn(game.turns, t),
        cast: applyTurnToCast(game.cast, t),
        clock: t.clock || game.clock,
        turn: Math.max(game.turn, t.turn),
        status: game.status === 'briefing' ? 'investigating' : game.status,
      },
    })
  }

  return {
    gameId: null,
    game: null,
    loading: false,
    error: null,
    pending: null,
    selection: EMPTY_SELECTION,
    confrontation: null,
    toasts: [],
    socketStatus: 'closed',
    guardEvents: [],
    debrief: null,
    liveMessage: '',

    // ---- lifecycle ------------------------------------------------------------------------
    loadGame: async (id) => {
      const switching = get().gameId !== id
      set({ loading: true, error: null, gameId: id, ...(switching ? { game: null, selection: EMPTY_SELECTION, confrontation: null, pending: null, debrief: null, guardEvents: [] } : {}) })
      try {
        const game = await api.getGame(id)
        set((s) => ({
          game,
          loading: false,
          selection: s.selection.primary && game.cast.some((c) => c.id === s.selection.primary) ? s.selection : { primary: game.cast[0]?.id ?? null, secondary: null },
        }))
        get().connect(id)
        return game
      } catch (e) {
        set({ loading: false })
        return fail(e, 'Could not load the game.')
      }
    },

    refreshGame: async () => {
      const id = get().gameId
      if (!id) return null
      try {
        const game = await api.getGame(id)
        // Keep any turns we have that the server response might lag behind (it should not, but be safe).
        const local = get().game
        const turns = local ? mergeTurns(game.turns, local.turns.filter((t) => t.turn > game.turn)) : game.turns
        set({ game: { ...game, turns } })
        return game
      } catch {
        return null
      }
    },

    connect: (id) => {
      const gameId = id ?? get().gameId
      if (!gameId) return
      if (socket && socketGameId === gameId) return
      socket?.close()
      socketGameId = gameId
      set({ socketStatus: 'connecting' })
      socket = connectGameSocket(gameId, (evt) => get().applyEvent(evt), {
        onStatus: (status) => set({ socketStatus: status }),
      })
    },

    disconnect: () => {
      socket?.close()
      socket = null
      socketGameId = null
      set({ socketStatus: 'closed' })
    },

    leaveGame: () => {
      get().disconnect()
      set({ gameId: null, game: null, loading: false, error: null, pending: null, selection: EMPTY_SELECTION, confrontation: null, debrief: null, guardEvents: [] })
    },

    // ---- player actions -------------------------------------------------------------------
    ask: async (text, suspectId) => {
      const id = get().gameId
      const sid = targetId(suspectId)
      const trimmed = text.trim()
      if (!id || !sid) return fail(new Error('Pick a suspect first.'), 'Pick a suspect first.')
      if (!trimmed) return fail(new Error('Type a question first.'), 'Type a question first.')
      return runTurn(id, sid, 'ask', { type: 'ask', suspect_id: sid, text: trimmed, player_signal: useSensors.getState().signal() })
    },

    present: async (evidenceId, suspectId) => {
      const id = get().gameId
      const sid = targetId(suspectId)
      if (!id || !sid) return fail(new Error('Pick a suspect first.'), 'Pick a suspect first.')
      return runTurn(id, sid, 'present', { type: 'present', suspect_id: sid, evidence_id: evidenceId, player_signal: useSensors.getState().signal() })
    },

    tactic: async (kind, text, suspectId) => {
      const id = get().gameId
      const sid = targetId(suspectId)
      if (!id || !sid) return fail(new Error('Pick a suspect first.'), 'Pick a suspect first.')
      const body: TurnRequest = { type: 'tactic', suspect_id: sid, tactic: kind, player_signal: useSensors.getState().signal() }
      const t = text?.trim()
      if (t) body.text = t
      return runTurn(id, sid, 'tactic', body)
    },

    confront: async (topic, rounds = 3, justWatch = false, pair) => {
      const id = get().gameId
      const sel = get().selection
      const a = pair?.a ?? sel.primary
      const b = pair?.b ?? sel.secondary
      if (!id || !a || !b || a === b) return fail(new Error('Select two suspects to confront.'), 'Select two suspects to confront.')
      const trimmed = topic.trim()
      if (!trimmed) return fail(new Error('Give the confrontation a topic.'), 'Give the confrontation a topic.')
      set({
        confrontation: { active: true, a, b, topic: trimmed, rounds, justWatch, lines: [], speaking: a, done: false, startedAt: Date.now() },
        pending: { suspectId: a, kind: 'confront', since: Date.now() },
        error: null,
      })
      try {
        const res = await api.postConfront(id, { a, b, topic: trimmed, rounds, player_signal: useSensors.getState().signal() })
        const lines = res.lines ?? []
        const game = get().game
        if (game) set({ game: { ...game, turns: mergeTurns(game.turns, lines), cast: lines.reduce(applyTurnToCast, game.cast), clock: lines[lines.length - 1]?.clock ?? game.clock } })
        set((s) => ({
          confrontation: s.confrontation ? { ...s.confrontation, lines: mergeTurns(s.confrontation.lines, lines), done: true, speaking: null } : s.confrontation,
          pending: null,
        }))
        void get().refreshGame()
        return lines
      } catch (e) {
        set((s) => ({ confrontation: s.confrontation ? { ...s.confrontation, done: true, speaking: null } : null }))
        return fail(e, 'The confrontation failed.')
      }
    },

    interject: async (text) => {
      const id = get().gameId
      const c = get().confrontation
      const trimmed = text.trim()
      if (!id || !c || !trimmed) return false
      try {
        await api.postInterject(id, trimmed)
        const game = get().game
        const last = c.lines[c.lines.length - 1]
        const local: PublicTurn = {
          turn: last?.turn ?? game?.turn ?? 0,
          seq: (last?.seq ?? 0) + 0.5,
          type: 'confront',
          actor: 'detective',
          target: null,
          detective_text: trimmed,
          clock: last?.clock ?? game?.clock ?? '',
        }
        set((s) => ({ confrontation: s.confrontation ? { ...s.confrontation, lines: mergeTurn(s.confrontation.lines, local) } : s.confrontation }))
        get().announce(`You interject: ${trimmed}`)
        return true
      } catch (e) {
        fail(e, 'Could not interject.')
        return false
      }
    },

    endConfrontation: () => {
      set({ confrontation: null, pending: null })
    },

    search: async (locationId) => {
      const id = get().gameId
      if (!id) return null
      set({ pending: { suspectId: '', kind: 'search', since: Date.now() }, error: null })
      try {
        const res = await api.postSearch(id, locationId)
        const game = get().game
        if (game) {
          const evidence = (res.evidence ?? []).reduce(upsertEvidence, game.evidence)
          const locations = game.locations.map((l) => (l.id === locationId ? { ...l, searched: true } : l))
          set({ game: { ...game, evidence, locations, clock: res.clock || game.clock } })
        }
        set({ pending: null })
        const found = res.evidence ?? []
        const locName = get().game?.locations.find((l) => l.id === locationId)?.name ?? 'the room'
        const text = found.length ? `Searched ${locName}: ${found.map((e) => e.name).join(', ')}.` : `Searched ${locName}: nothing new.`
        get().addToast({ kind: found.length ? 'success' : 'info', text, ttlMs: 6000 })
        get().announce(text)
        void get().refreshGame()
        return res
      } catch (e) {
        return fail(e, 'The search failed.')
      }
    },

    accuse: async (payload) => {
      const id = get().gameId
      if (!id) return null
      set({ pending: { suspectId: payload.suspect_id, kind: 'accuse', since: Date.now() }, error: null })
      try {
        const debrief = await api.postAccuse(id, payload)
        set((s) => ({ debrief, pending: null, game: s.game ? { ...s.game, status: 'closed' } : s.game }))
        return debrief
      } catch (e) {
        return fail(e, 'The accusation could not be filed.')
      }
    },

    loadDebrief: async (id) => {
      const gid = id ?? get().gameId
      if (!gid) return null
      try {
        const debrief = await api.getDebrief(gid)
        set({ debrief })
        return debrief
      } catch (e) {
        return fail(e, 'Could not load the debrief.')
      }
    },

    rewind: async (turn) => {
      const id = get().gameId
      if (!id) return null
      set({ loading: true, error: null })
      try {
        const game = await api.postRewind(id, turn)
        set({ game, loading: false, confrontation: null, pending: null, debrief: null })
        get().addToast({ kind: 'info', text: `Rewound to turn ${turn}.`, ttlMs: 5000 })
        return game
      } catch (e) {
        set({ loading: false })
        return fail(e, 'Rewind failed.')
      }
    },

    retry: async () => {
      const id = get().gameId
      if (!id) return null
      try {
        const res = await api.postRetry(id)
        return res.game_id
      } catch (e) {
        return fail(e, 'Could not start a new game on this case.')
      }
    },

    // ---- selection ------------------------------------------------------------------------
    select: (id, secondary = false) => {
      set((s) => {
        const sel = s.selection
        if (secondary) {
          if (!sel.primary || sel.primary === id) return { selection: { primary: id, secondary: null } }
          return { selection: { primary: sel.primary, secondary: sel.secondary === id ? null : id } }
        }
        return { selection: { primary: id, secondary: sel.secondary === id ? null : sel.secondary } }
      })
    },
    clearSelection: () => set({ selection: EMPTY_SELECTION }),

    // ---- events ---------------------------------------------------------------------------
    applyEvent: (evt) => {
      const game = get().game
      switch (evt.type) {
        case 'pending': {
          const sid = evt.suspect_id
          set((s) => ({
            pending: sid ? { suspectId: sid, kind: s.confrontation?.active ? 'confront' : (s.pending?.kind ?? 'ask'), since: Date.now() } : s.pending,
            confrontation: s.confrontation && sid ? { ...s.confrontation, speaking: sid } : s.confrontation,
          }))
          return
        }
        case 'turn_result': {
          mergeTurnIntoGame(evt.turn)
          set((s) => ({ pending: s.pending && s.pending.suspectId === evt.turn.actor ? null : s.pending }))
          const text = describeTurn(evt.turn, game?.cast ?? [])
          if (text) get().announce(text)
          return
        }
        case 'confront_line': {
          const line = evt.turn
          mergeTurnIntoGame(line)
          set((s) => ({
            confrontation: s.confrontation ? { ...s.confrontation, lines: mergeTurn(s.confrontation.lines, line), speaking: line.other ?? null } : s.confrontation,
            pending: s.confrontation ? (line.other ? { suspectId: line.other, kind: 'confront', since: Date.now() } : null) : s.pending,
          }))
          const text = describeTurn(line, game?.cast ?? [])
          if (text) get().announce(text)
          return
        }
        case 'confront_done': {
          set((s) => ({
            confrontation: s.confrontation ? { ...s.confrontation, done: true, speaking: null } : s.confrontation,
            pending: s.pending?.kind === 'confront' ? null : s.pending,
          }))
          return
        }
        case 'ticker': {
          if (!evt.text) return
          if (game) set({ game: { ...game, ticker: [...game.ticker, evt.text] } })
          get().addToast({ kind: 'ticker', kicker: 'Recent events', text: evt.text, ttlMs: 7000 })
          get().announce(evt.text)
          return
        }
        case 'clock': {
          if (game && evt.clock) set({ game: { ...game, clock: evt.clock } })
          return
        }
        case 'world_event': {
          if (game) {
            const evidence = evt.evidence ? upsertEvidence(game.evidence, evt.evidence) : game.evidence
            set({ game: { ...game, evidence, ticker: evt.text ? [...game.ticker, evt.text] : game.ticker } })
          }
          if (evt.text) {
            get().addToast({ kind: 'world', kicker: 'Something has changed', text: evt.text, ttlMs: 8000 })
            get().announce(evt.text)
          }
          return
        }
        case 'notebook_updated': {
          if (game) set({ game: { ...game, notebook: evt.notebook } })
          get().announce('Watson updated the notebook.')
          return
        }
        case 'guard_event': {
          set((s) => ({ guardEvents: [...s.guardEvents, evt.event].slice(-200) }))
          return
        }
        default:
          return
      }
    },

    addToast: (toast) => {
      const id = nextToastId()
      const full: Toast = { ttlMs: 6000, ...toast, id }
      set((s) => ({ toasts: [...s.toasts.slice(-4), full] }))
      return id
    },
    dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
    announce: (text) => set({ liveMessage: text }),
    setError: (message) => set({ error: message }),
  }

  /** Shared body of ask/present/tactic. */
  async function runTurn(gameId: string, suspectId: string, kind: PendingState['kind'], body: TurnRequest): Promise<PublicTurn | null> {
    set({ pending: { suspectId, kind, since: Date.now() }, error: null })
    try {
      const turn = await api.postTurn(gameId, body)
      mergeTurnIntoGame(turn)
      set({ pending: null })
      const text = describeTurn(turn, get().game?.cast ?? [])
      if (text) get().announce(text)
      void get().refreshGame()
      return turn
    } catch (e) {
      return fail(e, 'The suspect did not answer.')
    }
  }
})

// ---------------------------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------------------------

export const selectPrimarySuspect = (s: GameStoreState): PublicSuspect | null => s.game?.cast.find((c) => c.id === s.selection.primary) ?? null
export const selectSecondarySuspect = (s: GameStoreState): PublicSuspect | null => s.game?.cast.find((c) => c.id === s.selection.secondary) ?? null
export const selectIsPending = (s: GameStoreState): boolean => s.pending !== null
export const selectExaminedEvidence = (s: GameStoreState): PublicEvidence[] => s.game?.evidence.filter((e) => e.state === 'examined') ?? []
export const selectKnownEvidence = (s: GameStoreState): PublicEvidence[] => s.game?.evidence.filter((e) => e.state === 'known' || e.state === 'examined') ?? []

/** Turns involving a suspect (as speaker or target), for the dialogue log. */
export function turnsForSuspect(turns: PublicTurn[], suspectId: string): PublicTurn[] {
  return turns.filter((t) => t.actor === suspectId || t.target === suspectId || t.other === suspectId)
}

/** Cast index (0..n) for the suspect's accent colour (`.speaker-N`). */
export function speakerIndex(cast: PublicSuspect[], suspectId: string): number {
  const i = cast.findIndex((c) => c.id === suspectId)
  return i < 0 ? 0 : i % 5
}
