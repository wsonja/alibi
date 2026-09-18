/**
 * Game WebSocket — `connectGameSocket(gameId, onEvent)` with automatic reconnect (exponential backoff + jitter).
 *
 * The backend pushes JSON messages. We accept every envelope the backend lane might reasonably emit:
 *   {"type": "turn_result", "data": {...PublicTurn}}          (canonical)
 *   {"event": "turn_result", ...PublicTurn}                   (flattened — must use `event`, since PublicTurn has its own `type`)
 *   {"event": "ticker", "payload": {"text": "..."}}           (alternate key names)
 * and normalise to the `WsEvent` discriminated union in ./types.
 *
 * Path: `${API_BASE}/api/ws/games/{id}` first; if that never opens, `${API_BASE}/ws/games/{id}` is tried next.
 */
import { API_BASE } from './client'
import type { GuardEvent, NotebookEntry, PublicEvidence, PublicTurn, WsEvent } from './types'

export type SocketStatus = 'connecting' | 'open' | 'reconnecting' | 'closed'

export interface GameSocket {
  /** Stop reconnecting and close the underlying socket. */
  close(): void
  /** Current connection status. */
  readonly status: SocketStatus
  /** Send a JSON message to the server (rarely needed; the API is REST-first). Returns false if not open. */
  send(message: unknown): boolean
  /** The URL currently in use. */
  readonly url: string
}

export interface ConnectOptions {
  onStatus?: (status: SocketStatus) => void
  /** Initial reconnect delay in ms (default 1000). */
  minDelayMs?: number
  /** Max reconnect delay in ms (default 15000). */
  maxDelayMs?: number
  /** Override the candidate URLs (absolute ws:// or wss:// URLs). */
  urls?: string[]
}

function wsOrigin(): string {
  return API_BASE.replace(/^http/i, 'ws')
}

export function gameSocketUrls(gameId: string): string[] {
  const id = encodeURIComponent(gameId)
  const origin = wsOrigin()
  return [`${origin}/api/ws/games/${id}`, `${origin}/ws/games/${id}`]
}

type Rec = Record<string, unknown>

function isRec(v: unknown): v is Rec {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function looksLikeTurn(v: unknown): v is PublicTurn {
  return isRec(v) && typeof v.turn === 'number' && typeof v.actor === 'string' && typeof v.type === 'string'
}

/** Normalise any plausible server envelope into a WsEvent. Exported for tests and for the Investigation lane. */
export function normalizeWsMessage(raw: unknown): WsEvent {
  if (!isRec(raw)) return { type: 'unknown', raw }
  // `event` wins over `type`: a flattened PublicTurn carries its own `type` (ask|tactic|…), so a backend that
  // flattens must name the event with `event`. The canonical envelope is {type, data}.
  const name = typeof raw.event === 'string' ? raw.event : typeof raw.type === 'string' ? raw.type : null
  if (!name) return { type: 'unknown', raw }

  // Payload: prefer `data` / `payload`, else the message itself minus the discriminator keys.
  let payload: Rec
  if (isRec(raw.data)) payload = raw.data
  else if (isRec(raw.payload)) payload = raw.payload
  else {
    // Strip the discriminator; when the event was named by `event`, a `type` key belongs to the payload (PublicTurn.type).
    const { type: rawType, event: _e, ...rest } = raw
    void _e
    payload = typeof raw.event === 'string' && typeof rawType === 'string' ? { ...rest, type: rawType } : rest
  }

  switch (name) {
    case 'turn_result':
    case 'confront_line': {
      const t = looksLikeTurn(payload) ? payload : looksLikeTurn(payload.turn) ? payload.turn : looksLikeTurn(payload.line) ? payload.line : null
      if (!t) return { type: 'unknown', raw }
      return { type: name, turn: t }
    }
    case 'confront_done': {
      const turn = typeof payload.turn === 'number' ? payload.turn : Number(payload.turn ?? NaN)
      return { type: 'confront_done', turn: Number.isFinite(turn) ? turn : -1 }
    }
    case 'ticker':
      return { type: 'ticker', text: String(payload.text ?? payload.line ?? '') }
    case 'clock':
      return { type: 'clock', clock: String(payload.clock ?? payload.time ?? '') }
    case 'world_event':
      return {
        type: 'world_event',
        text: String(payload.text ?? ''),
        evidence: isRec(payload.evidence) ? (payload.evidence as unknown as PublicEvidence) : undefined,
      }
    case 'notebook_updated': {
      const nb = isRec(payload.notebook) ? payload.notebook : isRec(payload.entry) ? payload.entry : payload
      return { type: 'notebook_updated', notebook: nb as unknown as NotebookEntry }
    }
    case 'guard_event': {
      const ev = isRec(payload.event) ? payload.event : payload
      return { type: 'guard_event', event: ev as unknown as GuardEvent }
    }
    case 'pending':
      return { type: 'pending', suspect_id: String(payload.suspect_id ?? payload.suspect ?? '') }
    default:
      return { type: 'unknown', raw }
  }
}

/**
 * Open the game's event socket. `onEvent` receives normalised events. The returned handle reconnects on its own
 * until `close()` is called (or the page goes away).
 */
export function connectGameSocket(gameId: string, onEvent: (evt: WsEvent) => void, opts: ConnectOptions = {}): GameSocket {
  const urls = opts.urls && opts.urls.length ? opts.urls : gameSocketUrls(gameId)
  const minDelay = opts.minDelayMs ?? 1000
  const maxDelay = opts.maxDelayMs ?? 15_000

  let ws: WebSocket | null = null
  let status: SocketStatus = 'connecting'
  let attempt = 0
  let urlIndex = 0
  let everOpened = false
  let closedByUser = false
  let timer: ReturnType<typeof setTimeout> | null = null

  const setStatus = (s: SocketStatus) => {
    if (status === s) return
    status = s
    try {
      opts.onStatus?.(s)
    } catch {
      /* listener errors must not break the socket */
    }
  }

  const scheduleReconnect = () => {
    if (closedByUser) return
    setStatus('reconnecting')
    const base = Math.min(maxDelay, minDelay * 2 ** Math.min(attempt, 8))
    const jitter = Math.random() * base * 0.3
    attempt += 1
    timer = setTimeout(open, base + jitter)
  }

  const open = () => {
    if (closedByUser) return
    if (typeof WebSocket === 'undefined') {
      setStatus('closed')
      return
    }
    const url = urls[urlIndex % urls.length] ?? urls[0]!
    let openedThisAttempt = false
    try {
      ws = new WebSocket(url)
    } catch {
      urlIndex += 1
      scheduleReconnect()
      return
    }
    const sock = ws
    sock.onopen = () => {
      if (sock !== ws) return
      openedThisAttempt = true
      everOpened = true
      attempt = 0
      setStatus('open')
    }
    sock.onmessage = (ev: MessageEvent) => {
      if (sock !== ws) return
      let parsed: unknown
      try {
        parsed = typeof ev.data === 'string' ? JSON.parse(ev.data) : ev.data
      } catch {
        return
      }
      try {
        onEvent(normalizeWsMessage(parsed))
      } catch (e) {
        console.error('[ws] event handler threw', e)
      }
    }
    sock.onerror = () => {
      /* onclose follows; nothing to do here */
    }
    sock.onclose = () => {
      if (sock !== ws) return
      ws = null
      if (closedByUser) {
        setStatus('closed')
        return
      }
      // Never opened on this URL: rotate to the next candidate path before retrying.
      if (!openedThisAttempt && !everOpened) urlIndex += 1
      scheduleReconnect()
    }
  }

  open()

  return {
    get status() {
      return status
    },
    get url() {
      return urls[urlIndex % urls.length] ?? urls[0]!
    },
    send(message: unknown) {
      if (!ws || ws.readyState !== WebSocket.OPEN) return false
      try {
        ws.send(typeof message === 'string' ? message : JSON.stringify(message))
        return true
      } catch {
        return false
      }
    },
    close() {
      closedByUser = true
      if (timer) clearTimeout(timer)
      timer = null
      const sock = ws
      ws = null
      try {
        sock?.close(1000, 'client closed')
      } catch {
        /* ignore */
      }
      setStatus('closed')
    },
  }
}
