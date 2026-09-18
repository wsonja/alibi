/**
 * Debrief — route "/game/:id/debrief" (docs/DESIGN.md §5.6). CASE CLOSED: verdict, score, the truth, the reveal
 * reel (every suspect's lines coloured by honesty + their private reasoning), what you missed, case stats.
 *
 * Field names come from `Debrief` in @/api/types, cross-checked against a real accuse() response from the temp
 * backend (scripts/mock_api.py): a few `missed` fields carry richer objects at runtime than the `string[]` the
 * type declares (evidence_never_examined, secrets_never_revealed) — the helpers below read either shape safely.
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { Honesty, PublicSuspect, ReelNode } from '@/api/types'
import { PlayerAvatar } from '@/components/avatar/PlayerAvatar'
import { ButtonLink, Button } from '@/components/common/Button'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { Marquee } from '@/components/common/Marquee'
import { SectionTitle } from '@/components/common/SectionTitle'
import { PixelPortrait } from '@/components/portrait/PixelPortrait'
import { cn } from '@/lib/cn'
import { useGame } from '@/store/game'

/** Runtime `missed` entries are sometimes plain strings, sometimes objects — read whichever shows up. */
function labelOf(item: unknown): string {
  if (typeof item === 'string') return item
  if (item && typeof item === 'object') {
    const o = item as Record<string, unknown>
    if (typeof o.name === 'string') return o.name
    if (typeof o.text === 'string') return o.text
    if (typeof o.id === 'string') return o.id
  }
  return String(item)
}
function detailOf(item: unknown): string | undefined {
  if (item && typeof item === 'object') {
    const o = item as Record<string, unknown>
    if (typeof o.description === 'string') return o.description
    if (typeof o.text === 'string' && typeof o.name === 'string') return o.text
  }
  return undefined
}
function idOf(item: unknown): string | undefined {
  if (typeof item === 'string') return item
  if (item && typeof item === 'object') {
    const o = item as Record<string, unknown>
    if (typeof o.suspect_id === 'string') return o.suspect_id
  }
  return undefined
}

const HONESTY_COLOR: Record<string, string> = {
  truthful: 'var(--truth)',
  evasive: 'var(--deflect)',
  lie: 'var(--lie)',
}
const HONESTY_LABEL: Record<string, string> = { truthful: 'Truth', evasive: 'Deflection', lie: 'Lie' }

function HonestyChip({ honesty }: { honesty: Honesty | string }) {
  const color = HONESTY_COLOR[honesty] ?? 'var(--rumor)'
  return (
    <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#0b0806', background: color, marginBottom: 4 }}>
      {HONESTY_LABEL[honesty] ?? honesty}
    </span>
  )
}

function ReelRow({ node }: { node: ReelNode }) {
  return (
    <div className="lacquer lacquer--soft" style={{ padding: '8px 12px' }}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <HonestyChip honesty={node.honesty} />
        <span className="muted" style={{ fontSize: 11 }}>
          turn {node.turn} · stress {node.stress_before}→{node.stress_after}
          {node.guard_events?.length ? ' · 🛡 guarded' : ''}
        </span>
      </div>
      {node.detective_text ? (
        <p className="mono" style={{ margin: '4px 0', fontSize: 12, color: 'rgba(243,231,203,.7)' }}>
          You: {node.detective_text}
        </p>
      ) : null}
      <p style={{ margin: '4px 0' }}>{node.spoken}</p>
      {node.internal_reasoning ? (
        <p className="mono" style={{ margin: 0, fontSize: 12, fontStyle: 'italic', color: 'rgba(243,231,203,.6)' }}>
          🔍 {node.internal_reasoning}
        </p>
      ) : null}
    </div>
  )
}

function ReelColumn({ suspect, nodes }: { suspect: PublicSuspect; nodes: ReelNode[] }) {
  return (
    <div className="min-w-0" style={{ flex: '0 0 320px' }}>
      <div className="flex items-center gap-2 mb-2">
        <PixelPortrait suspect={suspect} emotion={suspect.emotion} size={48} />
        <div className="min-w-0">
          <div className="display display--gold" style={{ fontSize: 13 }}>
            {suspect.name}
          </div>
          <div className="muted" style={{ fontSize: 11, fontStyle: 'italic' }}>
            {suspect.role}
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {nodes.length === 0 ? <p className="muted" style={{ fontSize: 12 }}>Never questioned.</p> : nodes.map((n) => <ReelRow key={`${n.turn}:${n.seq}`} node={n} />)}
      </div>
    </div>
  )
}

export function Debrief() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const debrief = useGame((s) => s.debrief)
  const error = useGame((s) => s.error)
  const loadDebrief = useGame((s) => s.loadDebrief)
  const retry = useGame((s) => s.retry)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    if (id && (!debrief || debrief.game_id !== id)) void loadDebrief(id)
  }, [id, debrief, loadDebrief])

  const byCast = useMemo(() => {
    if (!debrief) return []
    return debrief.cast.map((s) => ({ suspect: s, nodes: debrief.reel.filter((n) => n.suspect_id === s.id) }))
  }, [debrief])

  async function handleRetry() {
    setRetrying(true)
    const newId = await retry()
    setRetrying(false)
    if (newId) navigate(`/game/${newId}/briefing`)
  }

  if (!debrief) {
    return (
      <div className="screen">
        <header className="flex justify-center">
          <Marquee />
        </header>
        {error ? (
          <div className="mt-6">
            <ErrorNotice message={error} onRetry={() => void loadDebrief(id)} />
          </div>
        ) : (
          <p className="mono muted text-center mt-8">Reading the case file…</p>
        )}
      </div>
    )
  }

  const d = debrief
  return (
    <div className="screen screen--wide">
      <header className="flex justify-center">
        <Marquee />
      </header>

      <section className="lacquer mt-6 text-center" style={{ borderColor: 'var(--marquee)' }}>
        <h1 className="display display--gold" style={{ fontSize: 26, margin: 0 }}>
          Case Closed
        </h1>
        <p className={cn('display', d.correct ? '' : '')} style={{ fontSize: 16, color: d.correct ? 'var(--truth)' : 'var(--lie)', margin: '6px 0' }}>
          {d.correct ? 'CORRECT! YOU FOUND THE TRUTH.' : 'WRONG. THE TRUTH WAS ELSEWHERE.'}
        </p>
        <div className="flex items-center justify-center gap-3">
          <PlayerAvatar size={48} silhouette={false} title="You" />
          <p className="muted" style={{ margin: 0 }}>
            Rank: <strong className="gold">{d.rank}</strong>
            {d.confidence_badge ? (
              <>
                {' '}
                · <span className="chip chip--dark selected">{d.confidence_badge}</span>
              </>
            ) : null}
          </p>
        </div>
        <div className="flex justify-center gap-6 mt-3 flex-wrap mono" style={{ fontSize: 13 }}>
          <span>Murderer {d.score.murderer}</span>
          <span>Method {d.score.method}</span>
          <span>Motive {d.score.motive}</span>
          <span className="gold" style={{ fontWeight: 700 }}>
            Total {d.score.total}
          </span>
        </div>
      </section>

      <section className="parchment mt-4">
        <SectionTitle as="h2" align="left">
          The Truth
        </SectionTitle>
        <p>
          The murderer was <strong>{d.truth.murderer_name}</strong>.
        </p>
        <p>
          <strong>Method:</strong> {d.truth.method}
        </p>
        <p>
          <strong>Motive:</strong> {d.truth.motive}
        </p>
        <h3 className="label-caps mt-3">True timeline</h3>
        <ol className="timeline">
          {d.truth.timeline_truth.map((t, i) => (
            <li key={i} className="timeline__item">
              <span className="timeline__time">{t.time}</span>
              <span className="timeline__event">{t.event}</span>
            </li>
          ))}
        </ol>
        {d.truth.red_herrings.length ? (
          <>
            <h3 className="label-caps mt-3">Red herrings</h3>
            <ul>
              {d.truth.red_herrings.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <section className="lacquer mt-4">
        <SectionTitle as="h2" dark align="left" subtitle="Every line, and what they were really thinking.">
          The Reveal Reel
        </SectionTitle>
        <div className="flex gap-4 scroll-x pb-2">
          {byCast.map(({ suspect, nodes }) => (
            <ReelColumn key={suspect.id} suspect={suspect} nodes={nodes} />
          ))}
        </div>
      </section>

      <section className="parchment mt-4">
        <SectionTitle as="h2" align="left">
          What You Missed
        </SectionTitle>
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <h3 className="label-caps">Evidence never examined</h3>
            {d.missed.evidence_never_examined.length === 0 ? (
              <p className="ink-soft" style={{ fontSize: 13 }}>
                None — you found it all.
              </p>
            ) : (
              <ul style={{ fontSize: 13 }}>
                {d.missed.evidence_never_examined.map((e, i) => (
                  <li key={i} title={detailOf(e)}>
                    {labelOf(e)}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3 className="label-caps">Secrets never revealed</h3>
            {d.missed.secrets_never_revealed.length === 0 ? (
              <p className="ink-soft" style={{ fontSize: 13 }}>
                None — you cracked everyone.
              </p>
            ) : (
              <ul style={{ fontSize: 13 }}>
                {d.missed.secrets_never_revealed.map((s, i) => {
                  const sid = idOf(s)
                  const name = d.cast.find((c) => c.id === sid)?.name ?? sid
                  return (
                    <li key={i}>
                      <strong>{name}:</strong> {labelOf(s)}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
          <div>
            <h3 className="label-caps">Near cracks</h3>
            {d.missed.near_cracks.length === 0 ? (
              <p className="ink-soft" style={{ fontSize: 13 }}>
                None.
              </p>
            ) : (
              <ul style={{ fontSize: 13 }}>
                {d.missed.near_cracks.map((n, i) => {
                  const name = d.cast.find((c) => c.id === n.suspect_id)?.name ?? n.suspect_id
                  return (
                    <li key={i}>
                      {name} nearly cracked at turn {n.turn} ({n.stress}/{n.threshold}).
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      </section>

      <section className="lacquer mt-4">
        <SectionTitle as="h2" dark align="left">
          Case Stats
        </SectionTitle>
        <div className="flex gap-6 flex-wrap mono" style={{ fontSize: 13 }}>
          <span>Turns used: {d.stats.turns}</span>
          <span>Clock: {d.stats.clock}</span>
          <span>Evidence found: {d.stats.evidence_pct}%</span>
          <span>Composure avg: {d.stats.composure_avg == null ? 'Camera off' : d.stats.composure_avg}</span>
        </div>
        <div className="flex gap-2 flex-wrap mt-2">
          {Object.entries(d.stats.tactics_used).map(([k, v]) => (
            <span key={k} className="chip chip--dark">
              {k}: {v}
            </span>
          ))}
        </div>
      </section>

      <div className="flex gap-3 flex-wrap mt-6 justify-center">
        <Button variant="black" loading={retrying} onClick={() => void handleRetry()}>
          ↻ Retry same case
        </Button>
        <ButtonLink to="/">👥 New case</ButtonLink>
      </div>
    </div>
  )
}

export default Debrief
