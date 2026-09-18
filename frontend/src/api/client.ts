/**
 * Typed fetch wrapper — one function per backend endpoint (docs/INTERFACES.md §6).
 *
 * Base URL: VITE_API_URL (default http://localhost:8000). Every function returns a typed promise and throws
 * `ApiError {status, message}`; a network failure (backend down) throws ApiError with status 0.
 */
import type {
  AccuseRequest,
  ApiErrorBody,
  ApiKeyResponse,
  CaseExport,
  CaseJob,
  CaseSummary,
  ConfrontRequest,
  ConfrontResponse,
  CreateGameRequest,
  CreateGameResponse,
  Debrief,
  DebugState,
  GameState,
  GameSummary,
  GenerateCaseRequest,
  GenerateCaseResponse,
  Health,
  ImportCaseResponse,
  InterjectResponse,
  PublicTurn,
  RetryResponse,
  SearchResponse,
  TurnRequest,
} from './types'

const rawBase = (import.meta.env.VITE_API_URL ?? '').trim()

/** Backend origin without a trailing slash, e.g. "http://localhost:8000". */
export const API_BASE: string = (rawBase || 'http://localhost:8000').replace(/\/+$/, '')

/** REST prefix. */
export const API_ROOT: string = `${API_BASE}/api`

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown
  readonly url: string

  constructor(status: number, message: string, url: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.url = url
    this.detail = detail
  }

  /** True when the backend could not be reached at all (connection refused, DNS, CORS, timeout). */
  get isNetwork(): boolean {
    return this.status === 0
  }

  get isNotFound(): boolean {
    return this.status === 404
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}

/** Human-readable message for any thrown value. */
export function errorMessage(e: unknown, fallback = 'Something went wrong.'): string {
  if (isApiError(e)) return e.message
  if (e instanceof Error && e.message) return e.message
  return fallback
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  /** Abort after this many milliseconds (default 60 s). */
  timeoutMs?: number
}

function messageFromBody(body: ApiErrorBody | null, status: number, statusText: string): string {
  if (body) {
    if (typeof body.error === 'string' && body.error) return body.error
    const d = body.detail
    if (typeof d === 'string' && d) return d
    if (Array.isArray(d)) {
      const parts = d
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg?: unknown }).msg) : ''))
        .filter(Boolean)
      if (parts.length) return parts.join('; ')
    }
    if (d && typeof d === 'object' && 'message' in (d as object)) {
      const m = (d as { message?: unknown }).message
      if (typeof m === 'string' && m) return m
    }
  }
  if (status === 404) return 'Not found.'
  if (status >= 500) return `The server hit an error (${status}).`
  return statusText ? `${status} ${statusText}` : `Request failed (${status}).`
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_ROOT}${path}`
  const controller = new AbortController()
  const timeoutMs = opts.timeoutMs ?? 60_000
  const timer = setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs)
  const onOuterAbort = () => controller.abort(opts.signal?.reason)
  opts.signal?.addEventListener('abort', onOuterAbort, { once: true })

  let res: Response
  try {
    res = await fetch(url, {
      method: opts.method ?? (opts.body !== undefined ? 'POST' : 'GET'),
      headers: opts.body !== undefined ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: controller.signal,
      credentials: 'omit',
    })
  } catch (e) {
    clearTimeout(timer)
    opts.signal?.removeEventListener('abort', onOuterAbort)
    const timedOut = e instanceof DOMException && e.name === 'TimeoutError'
    const aborted = e instanceof DOMException && e.name === 'AbortError'
    if (aborted) throw new ApiError(0, 'Request cancelled.', url, e)
    throw new ApiError(
      0,
      timedOut ? `The server took too long to answer (${Math.round(timeoutMs / 1000)} s).` : `Cannot reach the game server at ${API_BASE}. Is the backend running?`,
      url,
      e,
    )
  }
  clearTimeout(timer)
  opts.signal?.removeEventListener('abort', onOuterAbort)

  const text = await res.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = null
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, messageFromBody(parsed as ApiErrorBody | null, res.status, res.statusText), url, parsed ?? text)
  }
  return parsed as T
}

// ---------------------------------------------------------------------------------------------
// Health & settings
// ---------------------------------------------------------------------------------------------

export function health(opts?: { signal?: AbortSignal }): Promise<Health> {
  return request<Health>('/health', { signal: opts?.signal, timeoutMs: 8_000 })
}

/**
 * Sends a Gemini API key to the backend, which writes it into backend/.env and switches LLM mode.
 * The key is never logged or stored anywhere on the client.
 */
export function setApiKey(apiKey: string): Promise<ApiKeyResponse> {
  return request<ApiKeyResponse>('/settings/api-key', { body: { api_key: apiKey }, timeoutMs: 15_000 })
}

// ---------------------------------------------------------------------------------------------
// Cases
// ---------------------------------------------------------------------------------------------

export function listCases(opts?: { signal?: AbortSignal }): Promise<CaseSummary[]> {
  return request<CaseSummary[]>('/cases', { signal: opts?.signal, timeoutMs: 10_000 })
}

export function exportCase(caseId: string): Promise<CaseExport> {
  return request<CaseExport>(`/cases/${encodeURIComponent(caseId)}/export`)
}

/** URL of the share seed (case export JSON) — for "Share case seed". */
export function exportCaseUrl(caseId: string): string {
  return `${API_ROOT}/cases/${encodeURIComponent(caseId)}/export`
}

export function importCase(caseJson: unknown): Promise<ImportCaseResponse> {
  return request<ImportCaseResponse>('/cases/import', { body: { case: caseJson } })
}

export function generateCase(req: GenerateCaseRequest): Promise<GenerateCaseResponse> {
  return request<GenerateCaseResponse>('/cases/generate', { body: req, timeoutMs: 20_000 })
}

export function getCaseJob(jobId: string, opts?: { signal?: AbortSignal }): Promise<CaseJob> {
  return request<CaseJob>(`/cases/jobs/${encodeURIComponent(jobId)}`, { signal: opts?.signal, timeoutMs: 10_000 })
}

// ---------------------------------------------------------------------------------------------
// Games
// ---------------------------------------------------------------------------------------------

export function listGames(opts?: { signal?: AbortSignal }): Promise<GameSummary[]> {
  return request<GameSummary[]>('/games', { signal: opts?.signal, timeoutMs: 10_000 })
}

export function createGame(req: CreateGameRequest): Promise<CreateGameResponse> {
  return request<CreateGameResponse>('/games', { body: req, timeoutMs: 90_000 })
}

export function getGame(gameId: string, opts?: { signal?: AbortSignal }): Promise<GameState> {
  return request<GameState>(`/games/${encodeURIComponent(gameId)}`, { signal: opts?.signal, timeoutMs: 15_000 })
}

/** ask | tactic | present. Gemini turns can take a while — generous timeout. */
export function postTurn(gameId: string, req: TurnRequest): Promise<PublicTurn> {
  return request<PublicTurn>(`/games/${encodeURIComponent(gameId)}/turn`, { body: req, timeoutMs: 120_000 })
}

/** Runs the whole confrontation; lines are also streamed over the WebSocket as `confront_line`. */
export function postConfront(gameId: string, req: ConfrontRequest): Promise<ConfrontResponse> {
  return request<ConfrontResponse>(`/games/${encodeURIComponent(gameId)}/confront`, { body: req, timeoutMs: 300_000 })
}

export function postInterject(gameId: string, text: string): Promise<InterjectResponse> {
  return request<InterjectResponse>(`/games/${encodeURIComponent(gameId)}/confront/interject`, { body: { text }, timeoutMs: 15_000 })
}

export function postSearch(gameId: string, locationId: string): Promise<SearchResponse> {
  return request<SearchResponse>(`/games/${encodeURIComponent(gameId)}/search`, { body: { location_id: locationId }, timeoutMs: 30_000 })
}

export function postAccuse(gameId: string, req: AccuseRequest): Promise<Debrief> {
  return request<Debrief>(`/games/${encodeURIComponent(gameId)}/accuse`, { body: req, timeoutMs: 120_000 })
}

export function getDebrief(gameId: string, opts?: { signal?: AbortSignal }): Promise<Debrief> {
  return request<Debrief>(`/games/${encodeURIComponent(gameId)}/debrief`, { signal: opts?.signal, timeoutMs: 20_000 })
}

export function postRewind(gameId: string, turn: number): Promise<GameState> {
  return request<GameState>(`/games/${encodeURIComponent(gameId)}/rewind`, { body: { turn }, timeoutMs: 30_000 })
}

/** New game on the same case + difficulty. */
export function postRetry(gameId: string): Promise<RetryResponse> {
  return request<RetryResponse>(`/games/${encodeURIComponent(gameId)}/retry`, { body: {}, timeoutMs: 60_000 })
}

/** Full private state. 404 unless DEBUG_PANEL=1 on the backend. */
export function getDebug(gameId: string, opts?: { signal?: AbortSignal }): Promise<DebugState> {
  return request<DebugState>(`/games/${encodeURIComponent(gameId)}/debug`, { signal: opts?.signal, timeoutMs: 15_000 })
}

/** Convenience: resolves to the debug state, or null when the panel is disabled (404). Other errors propagate. */
export async function getDebugOrNull(gameId: string): Promise<DebugState | null> {
  try {
    return await getDebug(gameId)
  } catch (e) {
    if (isApiError(e) && e.isNotFound) return null
    throw e
  }
}

/** Everything in one object for lanes that prefer `api.xxx()` style. */
export const api = {
  health,
  setApiKey,
  listCases,
  exportCase,
  exportCaseUrl,
  importCase,
  generateCase,
  getCaseJob,
  listGames,
  createGame,
  getGame,
  postTurn,
  postConfront,
  postInterject,
  postSearch,
  postAccuse,
  getDebrief,
  postRewind,
  postRetry,
  getDebug,
  getDebugOrNull,
}

export default api
