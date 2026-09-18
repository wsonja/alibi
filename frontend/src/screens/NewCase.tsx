/**
 * NewCase — route "/" (docs/DESIGN.md §5.1).
 * Five setting tiles bound to GET /cases by preset; suspects / difficulty / accessibility / camera consent;
 * the big button creates the game (POST /games) or, for a tile without an installed case, generates one
 * (POST /cases/generate + polling GET /cases/jobs/:id) when the backend runs Live Gemini.
 * Degrades gracefully when the backend is unreachable: error toast with retry, offline status pill.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errorMessage, isApiError } from '@/api/client'
import type { CasePreset, CaseSummary, Difficulty, Health } from '@/api/types'
import { AvatarCapture } from '@/components/avatar/AvatarCapture'
import { PlayerAvatar } from '@/components/avatar/PlayerAvatar'
import { ApiKeyModal } from '@/components/common/ApiKeyModal'
import { Button } from '@/components/common/Button'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { Placard } from '@/components/common/Placard'
import { SceneThumb } from '@/components/common/SceneThumb'
import { SectionTitle } from '@/components/common/SectionTitle'
import { TypewriterProgress } from '@/components/common/TypewriterProgress'
import { ConsentGate } from '@/components/sensors/ConsentGate'
import { cn } from '@/lib/cn'
import { PRESET_TILES, casesForPreset, presetFromSetting } from '@/lib/presets'
import { truncate } from '@/lib/text'
import { useAvatar } from '@/store/avatar'
import { useGame } from '@/store/game'
import { useSensors } from '@/store/sensors'
import { A11Y_OPTIONS, useUI } from '@/store/ui'

type Phase = 'idle' | 'creating' | 'generating'

const SUSPECT_COUNTS = [3, 4, 5] as const
const DIFFICULTIES: ReadonlyArray<{ id: Difficulty; label: string; hint: string }> = [
  { id: 'rookie', label: 'Rookie', hint: 'Suspects crack sooner.' },
  { id: 'detective', label: 'Detective', hint: 'The intended experience.' },
  { id: 'inspector', label: 'Inspector', hint: 'Harder to rattle; rumours travel faster.' },
]

const CREATE_LINES = ['Opening the case file…', 'Seating the suspects…', 'Lighting the lamps…']
const GENERATE_SEED_LINES = ['Commissioning a new case…', 'Writing the cast…', 'Planting the evidence…', "Checking it's solvable…"]
const POLL_MS = 1500
const GENERATE_TIMEOUT_MS = 12 * 60 * 1000

export function NewCase() {
  const navigate = useNavigate()
  const addToast = useGame((s) => s.addToast)
  const a11y = useUI((s) => s.a11y)
  const toggleA11y = useUI((s) => s.toggleA11y)
  const accessibilityPayload = useUI((s) => s.accessibilityPayload)
  const consent = useSensors((s) => s.consent)
  const setConsent = useSensors((s) => s.setConsent)
  const hasAvatar = useAvatar((s) => s.grid !== null)
  const [captureOpen, setCaptureOpen] = useState(false)

  const [cases, setCases] = useState<CaseSummary[] | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadingCatalog, setLoadingCatalog] = useState(true)

  const [preset, setPreset] = useState<CasePreset>('manor')
  const [chosenSuspects, setNSuspects] = useState<number>(4)
  const [difficulty, setDifficulty] = useState<Difficulty>('detective')
  const [roomText, setRoomText] = useState('')

  const [phase, setPhase] = useState<Phase>('idle')
  const [progressLines, setProgressLines] = useState<string[]>([])
  const [progress, setProgress] = useState<number | null>(null)
  const [apiKeyOpen, setApiKeyOpen] = useState(false)

  const aliveRef = useRef(true)
  const abortRef = useRef<AbortController | null>(null)
  /** Latest versions of the async actions, so "Retry" toast buttons never capture a stale closure. */
  const actionsRef = useRef({ loadCatalog: async () => {}, createAndGo: async (_caseId: string) => {}, generateAndGo: async () => {} })
  useEffect(() => {
    aliveRef.current = true
    return () => {
      aliveRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  // ---- catalog ---------------------------------------------------------------------------
  const loadCatalog = useCallback(async () => {
    abortRef.current?.abort()
    const ctl = new AbortController()
    abortRef.current = ctl
    setLoadingCatalog(true)
    setLoadError(null)
    const [casesRes, healthRes] = await Promise.allSettled([api.listCases({ signal: ctl.signal }), api.health({ signal: ctl.signal })])
    if (!aliveRef.current || ctl.signal.aborted) return
    if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
    else setHealth(null)
    if (casesRes.status === 'fulfilled') {
      const normalised = casesRes.value.map((c) => ({ ...c, preset: c.preset ?? presetFromSetting(c.setting) }))
      setCases(normalised)
      setLoadError(null)
    } else {
      const msg = errorMessage(casesRes.reason, 'Could not load the case list.')
      setLoadError(msg)
      addToast({ kind: 'error', text: msg, ttlMs: 0, action: { label: 'Retry', onClick: () => void actionsRef.current.loadCatalog() } })
    }
    setLoadingCatalog(false)
  }, [addToast])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  // ---- derived ---------------------------------------------------------------------------
  const llmMode = health?.llm_mode ?? null
  const offline = cases === null && !loadingCatalog
  const tile = useMemo(() => PRESET_TILES.find((t) => t.id === preset) ?? PRESET_TILES[0]!, [preset])
  const installed = useMemo(() => (cases ? casesForPreset(cases, preset) : []), [cases, preset])
  const selectedCase: CaseSummary | null = installed[0] ?? null
  const otherCases = useMemo(() => (cases ? cases.filter((c) => c.preset === 'other') : []), [cases])
  const canGenerate = llmMode === 'gemini'
  const needsKey = !selectedCase && llmMode === 'scripted'
  const roomMissingText = preset === 'room' && !selectedCase && !roomText.trim()
  const busy = phase !== 'idle'
  const buttonLabel = selectedCase ? `✦ Begin: ${selectedCase.title} ✦` : '✦ Generate case ✦'
  const buttonDisabled = busy || offline || loadingCatalog || (!selectedCase && !canGenerate) || roomMissingText

  // hand-written cases fix the cast size
  const nSuspects = selectedCase?.n_suspects || chosenSuspects

  // ---- actions ---------------------------------------------------------------------------
  const createAndGo = useCallback(
    async (caseId: string) => {
      setPhase('creating')
      setProgress(null)
      setProgressLines([CREATE_LINES[0]!])
      const timers = [setTimeout(() => aliveRef.current && setProgressLines((l) => [...l, CREATE_LINES[1]!]), 700), setTimeout(() => aliveRef.current && setProgressLines((l) => [...l, CREATE_LINES[2]!]), 1500)]
      try {
        const res = await api.createGame({ case_id: caseId, difficulty, accessibility: accessibilityPayload(consent) })
        timers.forEach(clearTimeout)
        if (!aliveRef.current) return
        setProgress(1)
        navigate(`/game/${res.game_id}/briefing`)
      } catch (e) {
        timers.forEach(clearTimeout)
        if (!aliveRef.current) return
        setPhase('idle')
        setProgressLines([])
        const msg = errorMessage(e, 'Could not create the game.')
        addToast({ kind: 'error', text: msg, ttlMs: 0, action: { label: 'Retry', onClick: () => void actionsRef.current.createAndGo(caseId) } })
      }
    },
    [difficulty, accessibilityPayload, consent, navigate, addToast],
  )

  const generateAndGo = useCallback(async () => {
    const setting = preset === 'room' ? roomText.trim() : tile.generationSetting
    if (!setting) return
    setPhase('generating')
    setProgress(null)
    setProgressLines([GENERATE_SEED_LINES[0]!])
    let jobId: string
    try {
      const res = await api.generateCase({ setting, n_suspects: nSuspects, difficulty })
      jobId = res.job_id
    } catch (e) {
      if (!aliveRef.current) return
      setPhase('idle')
      setProgressLines([])
      const msg = isApiError(e) && e.status === 400 ? `${e.message} (generation needs Live Gemini)` : errorMessage(e, 'Could not start the Author.')
      addToast({ kind: 'error', text: msg, ttlMs: 0, action: { label: 'Retry', onClick: () => void actionsRef.current.generateAndGo() } })
      return
    }
    const started = Date.now()
    let consecutiveFailures = 0
    let seedIdx = 0
    while (aliveRef.current) {
      await new Promise((r) => setTimeout(r, POLL_MS))
      if (!aliveRef.current) return
      if (Date.now() - started > GENERATE_TIMEOUT_MS) {
        setPhase('idle')
        addToast({ kind: 'error', text: 'The Author is taking too long. Try again in a moment.', ttlMs: 0, action: { label: 'Retry', onClick: () => void actionsRef.current.generateAndGo() } })
        return
      }
      try {
        const job = await api.getCaseJob(jobId)
        consecutiveFailures = 0
        if (job.progress?.length) setProgressLines(job.progress)
        else if (seedIdx < GENERATE_SEED_LINES.length - 1) {
          seedIdx += 1
          setProgressLines(GENERATE_SEED_LINES.slice(0, seedIdx + 1))
        }
        if (job.status === 'done' && job.case_id) {
          setProgress(0.9)
          await loadCatalog()
          await createAndGo(job.case_id)
          return
        }
        if (job.status === 'failed') {
          setPhase('idle')
          addToast({ kind: 'error', text: job.error ? `The Author gave up: ${job.error}` : 'The Author could not write a solvable case.', ttlMs: 0, action: { label: 'Retry', onClick: () => void actionsRef.current.generateAndGo() } })
          return
        }
      } catch (e) {
        consecutiveFailures += 1
        if (consecutiveFailures >= 5) {
          setPhase('idle')
          addToast({ kind: 'error', text: errorMessage(e, 'Lost contact with the Author.'), ttlMs: 0, action: { label: 'Retry', onClick: () => void actionsRef.current.generateAndGo() } })
          return
        }
      }
    }
  }, [preset, roomText, tile.generationSetting, nSuspects, difficulty, addToast, loadCatalog, createAndGo])

  // "latest ref" pattern: retry buttons in toasts always call the current version of an action
  useEffect(() => {
    actionsRef.current = { loadCatalog, createAndGo, generateAndGo }
  })

  const begin = () => {
    if (buttonDisabled) return
    if (selectedCase) void createAndGo(selectedCase.id)
    else void generateAndGo()
  }

  const pillClass = offline ? 'status-pill--off' : llmMode === 'gemini' ? 'status-pill--live' : llmMode === 'scripted' ? 'status-pill--scripted' : ''
  const pillLabel = offline ? 'Suspects: Offline' : llmMode === 'gemini' ? 'Suspects: Live Gemini' : llmMode === 'scripted' ? 'Suspects: Scripted' : 'Suspects: …'

  return (
    <div className="screen screen--setup-art">
      <div>
        <section className="parchment slide-up setup-card--art relative" aria-labelledby="setup-title">
          <div className="archive-link">
            <Placard to="/archive" aria-label="Open the case archive">
              Case Archive
            </Placard>
          </div>
          <SectionTitle id="setup-title" as="h1">
            Setup — New Case
          </SectionTitle>

          {loadError && offline ? (
            <div className="mb-4">
              <ErrorNotice message={loadError} onRetry={() => void loadCatalog()} hint="Start it with `make backend` (port 8000), then retry." />
            </div>
          ) : null}

          {/* 1. Where */}
          <SectionTitle as="h2" align="left" subtitle="A new scene. A fresh set of secrets." className="mt-2">
            Where does this happen?
          </SectionTitle>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3" role="radiogroup" aria-label="Setting">
            {PRESET_TILES.map((t) => {
              const list = cases ? casesForPreset(cases, t.id) : []
              const has = list.length > 0
              const showRibbon = !has && !loadingCatalog && llmMode === 'scripted' // only when we know generation is unavailable
              return (
                <button
                  key={t.id}
                  type="button"
                  role="radio"
                  aria-checked={preset === t.id}
                  className={cn('tile', preset === t.id && 'selected', !has && !canGenerate && 'tile--dim')}
                  onClick={() => setPreset(t.id)}
                  disabled={busy}
                  title={has ? `${list[0]!.title} — ${truncate(list[0]!.setting, 90)}` : t.blurb}
                >
                  <SceneThumb preset={t.id} className="tile__scene" />
                  {showRibbon ? <span className="ribbon">Needs API key</span> : null}
                  <span className="tile__label">
                    {t.label}
                    {t.camera ? <span aria-hidden="true"> 📷</span> : null}
                    <span className="tile__sub">{has ? list[0]!.title : canGenerate ? 'Generate a new case' : t.blurb}</span>
                  </span>
                </button>
              )
            })}
            {otherCases.map((c) => (
              <button
                key={c.id}
                type="button"
                role="radio"
                aria-checked={preset === 'other' && selectedCase?.id === c.id}
                className={cn('tile', preset === 'other' && selectedCase?.id === c.id && 'selected')}
                onClick={() => setPreset('other')}
                disabled={busy}
                title={truncate(c.setting, 90)}
              >
                <SceneThumb preset="other" className="tile__scene" />
                <span className="tile__label">
                  {c.title}
                  <span className="tile__sub">{c.generated ? 'Generated case' : 'Imported case'}</span>
                </span>
              </button>
            ))}
          </div>

          <div className="mt-3 min-h-[28px]">
            {selectedCase ? (
              <p className="ink-soft" style={{ margin: 0, fontSize: 15 }}>
                <span className="label-caps">Installed case:</span> <em>{selectedCase.title}</em> — {truncate(selectedCase.setting, 140)}
              </p>
            ) : preset === 'room' && !offline ? (
              <label className="block">
                <span className="label-caps block mb-1">Describe where this happens</span>
                <textarea className="field" rows={3} value={roomText} onChange={(e) => setRoomText(e.target.value)} placeholder="A lighthouse keeper's cottage on the last night of the season. Five people came to dinner…" disabled={busy || !canGenerate} maxLength={600} />
              </label>
            ) : null}
            {needsKey ? (
              <p className="ink-soft" style={{ margin: '6px 0 0', fontSize: 14 }}>
                <span aria-hidden="true">🔑 </span>
                Procedural cases need a Gemini key.{' '}
                <button type="button" className="underline cursor-pointer" style={{ color: 'var(--red-600)' }} onClick={() => setApiKeyOpen(true)}>
                  Add one
                </button>{' '}
                or pick a tile with an installed case.
              </p>
            ) : !selectedCase && canGenerate && !offline ? (
              <p className="ink-soft" style={{ margin: '6px 0 0', fontSize: 14 }}>
                The Author will write a new case for this setting and the Checker will make sure it is solvable (about a minute).
              </p>
            ) : null}
          </div>

          <hr className="hr-wood" />

          {/* 2. How many */}
          <SectionTitle as="h2" align="left" subtitle="More people. More possibilities.">
            How many suspects?
          </SectionTitle>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Number of suspects">
            {SUSPECT_COUNTS.map((n) => (
              <button key={n} type="button" role="radio" aria-checked={nSuspects === n} className={cn('chip', nSuspects === n && 'selected')} onClick={() => setNSuspects(n)} disabled={busy || !!selectedCase}>
                {n}
              </button>
            ))}
            {selectedCase ? (
              <span className="ink-soft self-center" style={{ fontSize: 13 }}>
                Fixed by the case.
              </span>
            ) : null}
          </div>

          <hr className="hr-wood" />

          {/* 3. Difficulty */}
          <SectionTitle as="h2" align="left" subtitle="Same crimes. Deeper secrets.">
            Difficulty
          </SectionTitle>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Difficulty">
            {DIFFICULTIES.map((d) => (
              <button key={d.id} type="button" role="radio" aria-checked={difficulty === d.id} className={cn('chip', difficulty === d.id && 'selected')} onClick={() => setDifficulty(d.id)} disabled={busy} title={d.hint}>
                {d.label}
              </button>
            ))}
          </div>

          <hr className="hr-wood" />

          {/* 4. Accessibility */}
          <SectionTitle as="h2" align="left" subtitle="Mysteries for every mind.">
            Accessibility options
          </SectionTitle>
          <div className="flex flex-wrap gap-2">
            {A11Y_OPTIONS.map((opt) => (
              <label key={opt.key} className="toggle" title={opt.hint}>
                <input type="checkbox" className="toggle__input" checked={a11y[opt.key]} onChange={() => toggleA11y(opt.key)} disabled={busy} />
                <span className="toggle__track" aria-hidden="true" />
                <span className="toggle__icon" aria-hidden="true">
                  {opt.icon}
                </span>
                <span>{opt.label}</span>
              </label>
            ))}
          </div>

          <hr className="hr-wood" />

          {/* 5. Camera: your avatar + the sensors consent */}
          <SectionTitle as="h2" align="left" subtitle="Your face. A new clue.">
            Camera
          </SectionTitle>
          <div className="flex items-center gap-4 mb-3">
            <PlayerAvatar size={72} />
            <div className="min-w-0">
              <p className="ink" style={{ margin: 0, fontSize: 15 }}>
                {hasAvatar ? 'Your detective. Looking sharp.' : 'Take a photo and become the detective: a pixel portrait, made in your browser and never uploaded.'}
              </p>
              <Button variant="black" size="sm" className="mt-1" onClick={() => setCaptureOpen(true)} disabled={busy} title="Only a 36×42 grid of palette colours is kept; the photo itself is discarded.">
                📷 {hasAvatar ? 'Retake photo' : 'Take your photo'}
              </Button>
            </div>
          </div>
          <ConsentGate checked={consent} onChange={setConsent} disabled={busy} />

          <hr className="hr-gold" />

          {/* 6. The big button */}
          <div className="flex flex-col gap-3">
            <Button size="lg" block onClick={begin} disabled={buttonDisabled} loading={busy && phase === 'creating' && progress === 1} aria-describedby="begin-help">
              {buttonLabel}
            </Button>
            <p id="begin-help" className="sr-only">
              {selectedCase ? `Starts a new game of ${selectedCase.title} on ${difficulty} difficulty.` : 'Generates a new case for the selected setting, then starts the game.'}
            </p>
            {busy ? <TypewriterProgress active lines={progressLines} progress={progress} /> : null}
          </div>
        </section>
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-3 mt-6">
        <button type="button" className={cn('status-pill', pillClass)} onClick={() => (offline ? void loadCatalog() : setApiKeyOpen(true))} title={offline ? 'Retry connecting to the backend' : 'Set or change the Gemini API key'}>
          {pillLabel}
          {health && llmMode === 'gemini' ? <span className="muted"> · {health.models.suspect.split(',')[0]}</span> : null}
        </button>
        <span className="mono muted" style={{ fontSize: 11 }}>
          {health?.cases != null ? `${health.cases} case${health.cases === 1 ? '' : 's'} installed` : ''}
        </span>
      </footer>

      <ApiKeyModal open={apiKeyOpen} onClose={() => setApiKeyOpen(false)} currentMode={llmMode} onSaved={() => void loadCatalog()} />
      <AvatarCapture open={captureOpen} onClose={() => setCaptureOpen(false)} />
    </div>
  )
}

export default NewCase
