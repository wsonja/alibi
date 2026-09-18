/**
 * Investigation — route "/game/:id" (docs/DESIGN.md §5.3).
 * Three columns: SUSPECTS + LOCATIONS | THE ROOM (portrait, log, action bar) | NOTEBOOK + ACCUSE.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { TACTICS, type PublicEvidence, type PublicSuspect, type Tactic } from '@/api/types'
import { Button } from '@/components/common/Button'
import { ClockFace } from '@/components/common/ClockFace'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { EvidenceIcon } from '@/components/common/EvidenceIcon'
import { Marquee } from '@/components/common/Marquee'
import { Modal } from '@/components/common/Modal'
import { SectionTitle } from '@/components/common/SectionTitle'
import JudgePanel from '@/components/judge/JudgePanel'
import { PixelPortrait } from '@/components/portrait/PixelPortrait'
import { cn } from '@/lib/cn'
import { clockPhase, formatClock12 } from '@/lib/clock'
import { describeTurn, selectPrimarySuspect, selectSecondarySuspect, turnsForSuspect, useGame } from '@/store/game'
import { useUI, type ActionTab } from '@/store/ui'

const TABS: Array<{ key: ActionTab; label: string; hint: string }> = [
  { key: 'ask', label: '💬 Ask', hint: 'Ask a question' },
  { key: 'present', label: '📄 Present', hint: 'Show evidence' },
  { key: 'tactic', label: '🎭 Tactic', hint: 'Change approach' },
  { key: 'confront', label: '❗ Confront', hint: 'Challenge a lie' },
  { key: 'search', label: '🔍 Search', hint: 'Explore a room' },
]

const SEND_LABEL: Record<ActionTab, string> = {
  ask: 'SEND',
  present: 'PRESENT',
  tactic: 'USE TACTIC',
  confront: 'START CONFRONTATION',
  search: 'SEARCH',
}

function evidenceRank(e: PublicEvidence): number {
  if (e.state === 'examined') return 0
  if (e.state === 'known') return 1
  if (e.state === 'destroyed') return 2
  return 3
}

interface LogRow {
  id: string
  speaker: 'you' | 'suspect'
  text: string
  clock: string
}

/** Dialogue-log rows for one suspect: the question/action ("You:") then the reply ("<Name>:"), per turn. */
function buildLogRows(turns: ReturnType<typeof turnsForSuspect>, suspect: PublicSuspect, evidence: PublicEvidence[]): LogRow[] {
  const rows: LogRow[] = []
  for (const t of turns) {
    const key = `${t.turn}:${t.seq}`
    if (t.actor === 'detective') {
      if (t.detective_text) rows.push({ id: `${key}:you`, speaker: 'you', text: t.detective_text, clock: t.clock })
      continue
    }
    if (t.actor !== suspect.id) continue
    let youText = t.detective_text
    if (!youText && t.type === 'present' && t.evidence_id) {
      const ev = evidence.find((e) => e.id === t.evidence_id)
      youText = `Shows ${ev?.name ?? t.evidence_id}.`
    }
    if (!youText && t.type === 'tactic' && t.tactic) youText = `[${t.tactic}]`
    if (youText) rows.push({ id: `${key}:you`, speaker: 'you', text: youText, clock: t.clock })
    if (t.spoken) rows.push({ id: `${key}:them`, speaker: 'suspect', text: t.spoken, clock: t.clock })
  }
  return rows
}

export function Investigation() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const game = useGame((s) => s.game)
  const loading = useGame((s) => s.loading)
  const error = useGame((s) => s.error)
  const pending = useGame((s) => s.pending)
  const confrontation = useGame((s) => s.confrontation)
  const loadGame = useGame((s) => s.loadGame)
  const select = useGame((s) => s.select)
  const selection = useGame((s) => s.selection)
  const ask = useGame((s) => s.ask)
  const present = useGame((s) => s.present)
  const tactic = useGame((s) => s.tactic)
  const search = useGame((s) => s.search)
  const confront = useGame((s) => s.confront)
  const endConfrontation = useGame((s) => s.endConfrontation)
  const accuse = useGame((s) => s.accuse)
  const primary = useGame(selectPrimarySuspect)
  const secondary = useGame(selectSecondarySuspect)
  // Computed locally (not via a store selector) because a selector that returns a freshly-filtered array on every
  // call makes useSyncExternalStore see a "new" snapshot each render and loop forever (React: "Maximum update
  // depth exceeded" / "getSnapshot should be cached").
  const examined = useMemo(() => game?.evidence.filter((e) => e.state === 'examined') ?? [], [game])

  const tab = useUI((s) => s.actionTab)
  const setTab = useUI((s) => s.setActionTab)
  const toggleJudge = useUI((s) => s.toggleJudge)

  const [askText, setAskText] = useState('')
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null)
  const [selectedTactic, setSelectedTactic] = useState<Tactic | null>(null)
  const [tacticText, setTacticText] = useState('')
  const [confrontTopic, setConfrontTopic] = useState('')
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null)
  const [accuseOpen, setAccuseOpen] = useState(false)
  const logRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (id) void loadGame(id)
  }, [id, loadGame])

  useEffect(() => {
    if (game && game.status === 'closed') navigate(`/game/${id}/debrief`, { replace: true })
  }, [game, id, navigate])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const inField = e.target instanceof HTMLElement && ['INPUT', 'TEXTAREA'].includes(e.target.tagName)
      if (e.key === '`') {
        e.preventDefault()
        toggleJudge()
        return
      }
      if (inField) return
      if (e.key === 'a' || e.key === 'A') setAccuseOpen(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggleJudge])

  const isPending = pending !== null
  const primaryPending = !!primary && pending?.suspectId === primary.id

  const logRows = useMemo(() => (game && primary ? buildLogRows(turnsForSuspect(game.turns, primary.id), primary, game.evidence) : []), [game, primary])

  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logRows.length])

  const workingNotes = useMemo(() => (game ? game.turns.slice(-6).map((t) => describeTurn(t, game.cast)).filter(Boolean).reverse() : []), [game])

  const presentEvidence = useMemo(() => (game ? [...game.evidence].sort((a, b) => evidenceRank(a) - evidenceRank(b)) : []), [game])

  if (loading && !game) return <div className="screen screen--wide mono muted">Loading the room…</div>
  if (error && !game) {
    return (
      <div className="screen screen--wide">
        <ErrorNotice message={error} onRetry={() => void loadGame(id)} />
      </div>
    )
  }
  if (!game || !primary) return null

  async function handleSend() {
    if (isPending) return
    if (tab === 'ask') {
      const t = askText.trim()
      if (!t) return
      setAskText('')
      await ask(t)
    } else if (tab === 'present') {
      if (!selectedEvidence) return
      await present(selectedEvidence)
    } else if (tab === 'tactic') {
      if (!selectedTactic) return
      const t = tacticText.trim()
      setTacticText('')
      await tactic(selectedTactic, t || undefined)
    } else if (tab === 'confront') {
      const t = confrontTopic.trim()
      if (!t || !selection.secondary) return
      setConfrontTopic('')
      await confront(t, 3)
    } else if (tab === 'search') {
      if (!selectedLocation) return
      await search(selectedLocation)
    }
  }

  const sendDisabled =
    isPending ||
    (tab === 'ask' && !askText.trim()) ||
    (tab === 'present' && !selectedEvidence) ||
    (tab === 'tactic' && !selectedTactic) ||
    (tab === 'confront' && (!confrontTopic.trim() || !selection.secondary)) ||
    (tab === 'search' && !selectedLocation)

  const ticker = game.ticker[game.ticker.length - 1]

  return (
    <div className="screen screen--wide">
      <header className="flex items-center justify-between gap-4 flex-wrap">
        <Marquee small />
        <h1 className="display display--gold" style={{ fontSize: 20, margin: 0 }}>
          Investigation
        </h1>
        <span className="subtle-caps" style={{ color: 'rgba(243,231,203,.6)' }}>
          Question • Explore • Connect • Uncover
        </span>
      </header>

      <div className="grid gap-4 mt-4 lg:grid-cols-[20fr_55fr_25fr]">
        {/* LEFT — suspects + locations */}
        <div className="lacquer flex flex-col gap-3 min-w-0">
          <SectionTitle as="h2" dark align="left">
            Suspects {game.cast.length}
          </SectionTitle>
          <ul className="flex flex-col gap-2 list-none p-0 m-0">
            {game.cast.map((s) => {
              const locName = game.locations.find((l) => l.id === s.last_seen_location)?.name ?? s.last_seen_location
              return (
                <li key={s.id} className={cn('suspect-card', selection.primary === s.id && 'selected', selection.secondary === s.id && 'secondary')} style={{ cursor: 'default' }}>
                  <button
                    type="button"
                    className="flex-1 min-w-0 flex items-center gap-2 bg-transparent border-0 p-0 text-left cursor-pointer"
                    onClick={(e) => select(s.id, e.shiftKey)}
                    aria-pressed={selection.primary === s.id}
                  >
                    <PixelPortrait suspect={s} emotion={s.emotion} size={56} dim={pending?.suspectId === s.id} />
                    <span className="flex-1 min-w-0">
                      <span className="suspect-card__name block truncate">{s.name}</span>
                      <span className="suspect-card__meta block truncate">{s.role}</span>
                      <span className="pressure-label block mt-1">Pressure</span>
                      <span className="pressure-bar block" style={{ ['--pct' as string]: s.stress_pct }} aria-valuenow={s.stress_pct} role="meter" aria-valuemin={0} aria-valuemax={100} />
                      <span className="muted block truncate" style={{ fontSize: 11 }}>
                        📍 {locName}
                      </span>
                    </span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-black btn--sm"
                    style={{ flex: '0 0 auto', padding: '4px 8px' }}
                    title="Set as confrontation partner"
                    aria-label={`Set ${s.name} as the second suspect for confrontation`}
                    onClick={(e) => {
                      e.stopPropagation()
                      select(s.id, true)
                    }}
                  >
                    ⚔
                  </button>
                </li>
              )
            })}
          </ul>

          <hr className="hr-wood" style={{ margin: '4px 0' }} />
          <SectionTitle as="h2" dark align="left">
            Locations
          </SectionTitle>
          <ul className="flex flex-col gap-2 list-none p-0 m-0">
            {game.locations.map((l) => (
              <li key={l.id}>
                <button
                  type="button"
                  className={cn('chip chip--dark', selectedLocation === l.id && 'selected')}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                  onClick={() => {
                    setSelectedLocation(l.id)
                    setTab('search')
                  }}
                >
                  {l.searched ? '✓ ' : ''}
                  {l.name}
                </button>
              </li>
            ))}
          </ul>

          <hr className="hr-wood" style={{ margin: '4px 0' }} />
          <div className="flex items-center gap-3">
            <ClockFace time={game.clock} size={48} dawn={game.clock >= '05:00' && game.clock < '12:00'} />
            <div className="min-w-0">
              <div style={{ fontSize: 14 }}>
                {formatClock12(game.clock)} · {clockPhase(game.clock)}
              </div>
              {ticker ? (
                <div className="muted fade-in truncate" style={{ fontSize: 12 }} title={ticker}>
                  {ticker}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {/* CENTRE — the room */}
        <div className="lacquer flex flex-col gap-3 min-w-0">
          <SectionTitle as="h2" dark>
            The Room
          </SectionTitle>

          {confrontation ? (
            <div className="lacquer lacquer--soft flex flex-col gap-2">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="display display--gold" style={{ fontSize: 13 }}>
                  {game.cast.find((c) => c.id === confrontation.a)?.name ?? confrontation.a} ⚔ {game.cast.find((c) => c.id === confrontation.b)?.name ?? confrontation.b}
                </span>
                <span className="muted" style={{ fontSize: 12 }}>
                  “{confrontation.topic}”
                </span>
                {confrontation.done ? (
                  <Button variant="black" size="sm" onClick={endConfrontation}>
                    Back to the room
                  </Button>
                ) : null}
              </div>
              <div className="dialogue-log" style={{ maxHeight: 180 }}>
                {confrontation.lines.map((l) => (
                  <div key={`${l.turn}:${l.seq}`} className="dialogue-log__row">
                    <span className="dialogue-log__who">{l.actor === 'detective' ? 'You' : (game.cast.find((c) => c.id === l.actor)?.name ?? l.actor)}</span>
                    <span className="dialogue-log__text">{l.spoken ?? l.detective_text}</span>
                    <span className="dialogue-log__time">{l.clock}</span>
                  </div>
                ))}
                {!confrontation.done ? <p className="mono muted">{confrontation.speaking ? `${game.cast.find((c) => c.id === confrontation.speaking)?.name ?? '…'} is speaking…` : '…'}</p> : null}
              </div>
            </div>
          ) : null}

          <div className="flex items-start gap-4 flex-wrap">
            <PixelPortrait suspect={primary} emotion={primary.emotion} size={160} dim={primaryPending} />
            <div className="min-w-0 flex-1">
              <h3 className="display display--gold" style={{ fontSize: 16, margin: 0 }}>
                {primary.name}
              </h3>
              <p className="muted" style={{ margin: '2px 0 8px', fontStyle: 'italic' }}>
                {primary.role}
              </p>
              {primaryPending ? (
                <p className="mono muted">…</p>
              ) : primary.tell ? (
                <p style={{ fontStyle: 'italic', margin: 0, color: 'rgba(243,231,203,.75)' }}>{primary.tell}</p>
              ) : null}
            </div>
          </div>

          <div className="speech-panel">{primaryPending ? '…' : (logRows.filter((r) => r.speaker === 'suspect').slice(-1)[0]?.text ?? 'Nothing said yet. Ask a question.')}</div>

          <div ref={logRef} className="dialogue-log" style={{ maxHeight: 240, minHeight: 120 }} aria-live="off">
            {logRows.length === 0 ? <p className="mono muted">No conversation yet with {primary.name}.</p> : null}
            {logRows.map((r) => (
              <div key={r.id} className="dialogue-log__row speaker-0">
                <span className="dialogue-log__who">{r.speaker === 'you' ? 'You' : primary.name}</span>
                <span className="dialogue-log__text">{r.text}</span>
                <span className="dialogue-log__time">{r.clock}</span>
              </div>
            ))}
          </div>

          {/* Action bar */}
          <div className="tab-bar" role="tablist">
            {TABS.map((t) => (
              <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} className={cn('tab', tab === t.key && 'active')} onClick={() => setTab(t.key)}>
                {t.label}
                <span className="tab__hint">{t.hint}</span>
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-2">
            {tab === 'ask' ? (
              <input
                type="text"
                className="field"
                placeholder="Ask a question…"
                value={askText}
                onChange={(e) => setAskText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void handleSend()
                  }
                }}
                disabled={isPending}
              />
            ) : null}

            {tab === 'present' ? (
              <div className="flex gap-2 flex-wrap">
                {presentEvidence.length === 0 ? <p className="muted">No evidence known yet — search the rooms.</p> : null}
                {presentEvidence.map((e) => {
                  const disabled = e.state !== 'examined' && e.state !== 'known'
                  return (
                    <button
                      key={e.id}
                      type="button"
                      className={cn('chip chip--dark', selectedEvidence === e.id && 'selected')}
                      disabled={disabled}
                      onClick={() => setSelectedEvidence(e.id)}
                      title={e.state === 'examined' ? e.examined_detail : e.description}
                    >
                      <EvidenceIcon name={e.name} description={e.description} size={16} />
                      {e.name}
                    </button>
                  )
                })}
              </div>
            ) : null}

            {tab === 'tactic' ? (
              <div className="flex flex-col gap-2">
                <div className="flex gap-2 flex-wrap">
                  {TACTICS.map((tKind) => (
                    <button key={tKind} type="button" className={cn('chip', selectedTactic === tKind && 'selected')} onClick={() => setSelectedTactic(tKind)}>
                      {tKind[0]!.toUpperCase() + tKind.slice(1)}
                    </button>
                  ))}
                </div>
                <input type="text" className="field" placeholder="Optional line to say…" value={tacticText} onChange={(e) => setTacticText(e.target.value)} disabled={isPending} />
              </div>
            ) : null}

            {tab === 'confront' ? (
              <div className="flex flex-col gap-2">
                <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                  {selection.secondary ? (
                    <>
                      {primary.name} ⚔ {secondary?.name}
                    </>
                  ) : (
                    'Shift-click a suspect, or use the ⚔ button, to pick a second suspect.'
                  )}
                </p>
                <input type="text" className="field" placeholder="Confrontation topic…" value={confrontTopic} onChange={(e) => setConfrontTopic(e.target.value)} disabled={isPending || !selection.secondary} />
              </div>
            ) : null}

            {tab === 'search' ? (
              <p className="muted" style={{ margin: 0 }}>
                {selectedLocation ? <>Search {game.locations.find((l) => l.id === selectedLocation)?.name}?</> : 'Pick a location on the left.'}
              </p>
            ) : null}

            <Button variant="red" size="lg" block loading={isPending} disabled={sendDisabled} onClick={() => void handleSend()}>
              {SEND_LABEL[tab]}
            </Button>
          </div>
        </div>

        {/* RIGHT — notebook + accuse */}
        <div className="parchment flex flex-col gap-3 min-w-0">
          <SectionTitle as="h2" align="left">
            Notebook
          </SectionTitle>
          <ul className="flex flex-col gap-2 list-none p-0 m-0">
            {game.evidence.map((e) => (
              <li key={e.id} className={cn(e.state !== 'examined' && e.state !== 'known' ? 'hidden' : '')} style={{ opacity: e.state === 'examined' ? 1 : 0.55 }}>
                <div className="flex items-start gap-2">
                  <EvidenceIcon name={e.name} description={e.description} size={18} color="var(--wood-600)" />
                  <div className="min-w-0">
                    <div style={{ fontWeight: 700, fontSize: 13 }}>{e.name}</div>
                    <div style={{ fontSize: 12 }}>{e.state === 'examined' && e.examined_detail ? e.examined_detail : e.description}</div>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <hr className="hr-wood" style={{ margin: '4px 0' }} />
          <h3 className="label-caps" style={{ margin: 0 }}>
            Working notes
          </h3>
          <ul className="flex flex-col gap-1 list-none p-0 m-0" style={{ fontSize: 13 }}>
            {workingNotes.length === 0 ? <li className="ink-soft">Nothing yet. Ask someone something.</li> : null}
            {workingNotes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>

          <div className="mt-auto">
            <Button variant="red" size="lg" block onClick={() => setAccuseOpen(true)}>
              ⚖ Accuse
            </Button>
          </div>
        </div>
      </div>

      <AccuseModal
        open={accuseOpen}
        onClose={() => setAccuseOpen(false)}
        cast={game.cast}
        examined={examined}
        pending={isPending}
        onAccuse={async (payload) => {
          const debrief = await accuse(payload)
          if (debrief) {
            setAccuseOpen(false)
            navigate(`/game/${id}/debrief`)
          }
        }}
      />

      <JudgePanel gameId={id} />
    </div>
  )
}

interface AccuseModalProps {
  open: boolean
  onClose: () => void
  cast: PublicSuspect[]
  examined: PublicEvidence[]
  pending: boolean
  onAccuse: (payload: { suspect_id: string; method_evidence_ids: string[]; motive_text: string; confidence: number }) => Promise<void>
}

function AccuseModal({ open, onClose, cast, examined, pending, onAccuse }: AccuseModalProps) {
  const [suspectId, setSuspectId] = useState<string | null>(null)
  const [evidenceIds, setEvidenceIds] = useState<string[]>([])
  const [motive, setMotive] = useState('')
  const [confidence, setConfidence] = useState(0.5)

  useEffect(() => {
    if (!open) {
      setSuspectId(null)
      setEvidenceIds([])
      setMotive('')
      setConfidence(0.5)
    }
  }, [open])

  function toggleEvidence(id: string) {
    setEvidenceIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const canAccuse = !!suspectId && !pending  // evidence and motive are optional: they only add points

  return (
    <Modal open={open} onClose={onClose} title="☞ ✦ Accuse ✦ — it all comes down to this" width={720}>
      <div className="flex flex-col gap-4">
        <div>
          <h3 className="label-caps" style={{ margin: '0 0 6px' }}>
            1. The suspect — who did it?
          </h3>
          <div className="flex gap-3 flex-wrap">
            {cast.map((s) => (
              <button key={s.id} type="button" className={cn('suspect-card', suspectId === s.id && 'selected')} style={{ width: 140, flexDirection: 'column', textAlign: 'center' }} onClick={() => setSuspectId(s.id)}>
                <PixelPortrait suspect={s} emotion={s.emotion} size={56} />
                <span className="suspect-card__name">{s.name}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <h3 className="label-caps" style={{ margin: '0 0 6px' }}>
            2. The method — how did they do it?
          </h3>
          {examined.length === 0 ? (
            <p className="ink-soft" style={{ margin: 0 }}>
              No evidence examined yet. You can still accuse, but the method scores 0 until you present examined evidence.
            </p>
          ) : (
            <div className="flex gap-2 flex-wrap">
              {examined.map((e) => (
                <button key={e.id} type="button" className={cn('chip', evidenceIds.includes(e.id) && 'selected')} onClick={() => toggleEvidence(e.id)} title={e.examined_detail ?? e.description}>
                  {e.name}
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <h3 className="label-caps" style={{ margin: '0 0 6px' }}>
            3. The motive — why did they do it?
          </h3>
          <textarea className="field" placeholder="Type your theory…" value={motive} onChange={(e) => setMotive(e.target.value)} rows={3} />
        </div>

        <div>
          <h3 className="label-caps" style={{ margin: '0 0 6px' }}>
            4. How sure are you?
          </h3>
          <input type="range" className="slider" min={0} max={1} step={0.05} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} />
          <div className="flex justify-between muted" style={{ fontSize: 11 }}>
            <span>Not sure</span>
            <span>A hunch</span>
            <span>Pretty sure</span>
            <span>Certain</span>
          </div>
        </div>

        <p className="ink" style={{ textAlign: 'center', fontWeight: 700 }}>
          ⚠ This ends the investigation. ⚠
        </p>

        <div className="flex gap-3 justify-end">
          <Button variant="black" onClick={onClose}>
            Not yet
          </Button>
          <Button
            variant="red"
            loading={pending}
            disabled={!canAccuse}
            onClick={() => {
              if (!suspectId) return
              void onAccuse({ suspect_id: suspectId, method_evidence_ids: evidenceIds, motive_text: motive.trim(), confidence })
            }}
          >
            ☞ Accuse
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default Investigation
