/**
 * Briefing — route "/game/:id/briefing" (docs/DESIGN.md §5.2), from GET /games/:id.
 * Left: what happened, public timeline, time of death, crime scene. Right: the suspects (2×2, alibi bubbles).
 * Bottom: initial evidence strip and BEGIN INVESTIGATION.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { PublicEvidence, PublicLocation, PublicSuspect } from '@/api/types'
import { Button, ButtonLink } from '@/components/common/Button'
import { ClockFace } from '@/components/common/ClockFace'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { EvidenceIcon } from '@/components/common/EvidenceIcon'
import { Marquee } from '@/components/common/Marquee'
import { SceneThumb } from '@/components/common/SceneThumb'
import { SectionTitle } from '@/components/common/SectionTitle'
import { Sticky } from '@/components/common/Sticky'
import { PixelPortrait } from '@/components/portrait/PixelPortrait'
import { cn } from '@/lib/cn'
import { formatClock12 } from '@/lib/clock'
import { presetFromSetting } from '@/lib/presets'
import { deriveCrimeScene, deriveDeathWindow, extractAlibi, numberWord } from '@/lib/text'
import { useGame } from '@/store/game'

function SuspectCard({ suspect }: { suspect: PublicSuspect }) {
  const [pinned, setPinned] = useState(false)
  const alibi = useMemo(() => extractAlibi(suspect.public_description), [suspect.public_description])
  return (
    <li className="relative group">
      <article className={cn('lacquer lacquer--soft h-full flex flex-col items-center text-center gap-2 fade-in', pinned && 'glow-pulse')} style={{ padding: '14px 12px' }} aria-label={`${suspect.name}, ${suspect.role}`}>
        <PixelPortrait suspect={suspect} emotion={suspect.emotion} size={96} />
        <h3 className="display display--gold" style={{ fontSize: 13, margin: 0 }}>
          {suspect.name}
        </h3>
        <p className="muted" style={{ margin: 0, fontStyle: 'italic', fontSize: 14 }}>
          {suspect.role}
        </p>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.4, color: 'rgba(243,231,203,.85)' }}>{suspect.public_description}</p>
        <button type="button" className="btn btn-black btn--sm mt-auto" onClick={() => setPinned((p) => !p)} aria-pressed={pinned} aria-label={`${pinned ? 'Hide' : 'Show'} the stated alibi of ${suspect.name}`}>
          <span aria-hidden="true">🔍</span> Alibi
        </button>
      </article>
      <div className={cn('speech-bubble speech-bubble--top absolute left-2 right-2 -bottom-3 translate-y-full z-10 transition-opacity', pinned ? 'opacity-100' : 'opacity-0 pointer-events-none group-hover:opacity-100 group-focus-within:opacity-100')} role="note" aria-hidden={!pinned}>
        <span className="speech-bubble__label">Alibi (public)</span>“{alibi}”
      </div>
    </li>
  )
}

function EvidenceStrip({ evidence, locations }: { evidence: PublicEvidence[]; locations: PublicLocation[] }) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [overflow, setOverflow] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const check = () => setOverflow(el.scrollWidth > el.clientWidth + 4)
    check()
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(check) : null
    ro?.observe(el)
    return () => ro?.disconnect()
  }, [evidence.length])
  const scroll = (dir: 1 | -1) => ref.current?.scrollBy({ left: dir * 300, behavior: 'smooth' })
  const locName = (id: string) => locations.find((l) => l.id === id)?.name ?? id
  return (
    <div className="relative">
      {overflow ? (
        <button type="button" className="btn btn-black btn--sm absolute left-0 top-1/2 -translate-y-1/2 z-10" onClick={() => scroll(-1)} aria-label="Scroll evidence left">
          ◀
        </button>
      ) : null}
      <div ref={ref} className="scroll-x flex gap-3 py-2 px-1" role="list" aria-label="Initial evidence">
        {evidence.length === 0 ? <p className="ink-soft">No evidence is known yet. Search the rooms.</p> : null}
        {evidence.map((e) => (
          <div key={e.id} className={cn('evidence-card', e.state === 'examined' && 'evidence-card--examined')} role="listitem">
            <EvidenceIcon name={e.name} description={e.description} size={30} color="#e0bc63" />
            <span className="evidence-card__name">{e.name}</span>
            <span className="evidence-card__where">📍 {locName(e.location)}</span>
            <span style={{ fontSize: 12, color: 'rgba(243,231,203,.75)' }}>{e.state === 'examined' && e.examined_detail ? e.examined_detail : e.description}</span>
          </div>
        ))}
      </div>
      {overflow ? (
        <button type="button" className="btn btn-black btn--sm absolute right-0 top-1/2 -translate-y-1/2 z-10" onClick={() => scroll(1)} aria-label="Scroll evidence right">
          ▶
        </button>
      ) : null}
    </div>
  )
}

export function Briefing() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const game = useGame((s) => s.game)
  const loading = useGame((s) => s.loading)
  const error = useGame((s) => s.error)
  const loadGame = useGame((s) => s.loadGame)
  const [sceneOpen, setSceneOpen] = useState(false)

  useEffect(() => {
    if (id) void loadGame(id)
  }, [id, loadGame])

  const ready = game && game.game_id === id ? game : null
  const death = useMemo(() => (ready ? deriveDeathWindow(ready.case.timeline_public, ready.case.victim.cause_of_death_public) : null), [ready])
  const scene = useMemo(() => (ready ? deriveCrimeScene(ready.locations, ready.evidence, ready.case.briefing) : null), [ready])
  const initialEvidence = useMemo(() => (ready ? ready.evidence.filter((e) => e.state === 'known' || e.state === 'examined') : []), [ready])
  const preset = ready ? presetFromSetting(ready.case.setting) : 'other'
  const n = ready?.cast.length ?? 0

  return (
    <div className="screen screen--wide">
      <header className="flex justify-center">
        <Marquee />
      </header>

      {!ready && loading ? (
        <div className="lacquer mono muted mt-8 text-center" aria-busy="true" style={{ maxWidth: 480, margin: '32px auto' }}>
          Opening the case file…
        </div>
      ) : null}
      {!ready && !loading && error ? (
        <div className="mt-8" style={{ maxWidth: 640, margin: '32px auto' }}>
          <ErrorNotice message={error} onRetry={() => void loadGame(id)} />
        </div>
      ) : null}

      {ready ? (
        <section className="parchment mt-6 slide-up" aria-labelledby="briefing-title">
          <SectionTitle id="briefing-title" as="h1" subtitle="Same roof. Different truths.">
            Briefing — The Crime
          </SectionTitle>
          <p className="text-center ink-soft" style={{ margin: '-6px 0 16px', fontStyle: 'italic' }}>
            {ready.case.title} · {ready.case.setting}
          </p>

          <div className="grid gap-6 lg:grid-cols-[55fr_45fr]">
            {/* LEFT */}
            <div className="min-w-0">
              <h2 className="label-caps" style={{ fontSize: 13, marginTop: 0 }}>
                ✜ What happened?
              </h2>
              {ready.case.briefing.split(/\n{2,}/).map((para, i) => (
                <p key={i} style={{ fontSize: 18, lineHeight: 1.55 }}>
                  {para}
                </p>
              ))}

              <div className="lacquer lacquer--soft mt-3 flex gap-3 items-start" style={{ padding: '10px 12px' }}>
                <span aria-hidden="true" style={{ fontSize: 22 }}>
                  ☠
                </span>
                <div>
                  <span className="label-caps label-caps--gold">The victim — {ready.case.victim.name}</span>
                  <p style={{ margin: '2px 0 4px', fontSize: 14 }}>{ready.case.victim.description}</p>
                  <p className="muted" style={{ margin: 0, fontSize: 13, fontStyle: 'italic' }}>
                    {ready.case.victim.cause_of_death_public}
                  </p>
                </div>
              </div>

              <h3 className="label-caps mt-4" style={{ fontSize: 12 }}>
                Public timeline
              </h3>
              <ol className="timeline">
                {ready.case.timeline_public.map((t, i) => (
                  <li key={`${t.time}-${i}`} className="timeline__item">
                    <span className="timeline__time">{t.time}</span>
                    <span className="timeline__event">{t.event}</span>
                  </li>
                ))}
              </ol>

              <div className="grid gap-3 sm:grid-cols-2 mt-4">
                <div className="lacquer lacquer--soft flex items-center gap-3">
                  <ClockFace time={death?.to ?? ready.clock} size={64} />
                  <div>
                    <span className="label-caps label-caps--gold">Time of death</span>
                    <div style={{ fontSize: 16 }}>{death ? `Between ${death.label}` : 'Not yet established'}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      Your clock: {formatClock12(ready.clock)}
                    </div>
                  </div>
                </div>
                <div className="lacquer lacquer--soft flex items-center gap-3">
                  <SceneThumb preset={preset} className="rounded" style={{ width: 96, height: 60, flex: '0 0 auto', border: '1px solid var(--gold-500)' }} />
                  <div className="min-w-0">
                    <span className="label-caps label-caps--gold">Crime scene: {scene?.name ?? 'unknown'}</span>
                    <div>
                      <button type="button" className="underline cursor-pointer" style={{ color: 'var(--gold-300)', fontSize: 14 }} onClick={() => setSceneOpen((o) => !o)} aria-expanded={sceneOpen}>
                        📍 View location
                      </button>
                    </div>
                    {sceneOpen && scene ? (
                      <p className="muted fade-in" style={{ margin: '4px 0 0', fontSize: 13 }}>
                        {scene.description}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>

            {/* RIGHT */}
            <div className="min-w-0">
              <SectionTitle as="h2" align="left" subtitle={`${numberWord(n)} people. ${numberWord(n)} versions.`}>
                The suspects
              </SectionTitle>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-4 list-none p-0 m-0 pb-10">
                {ready.cast.map((s) => (
                  <SuspectCard key={s.id} suspect={s} />
                ))}
              </ul>
              <div className="hidden xl:flex justify-end mt-2">
                <Sticky>Hover a suspect to hear their story. Then doubt it.</Sticky>
              </div>
            </div>
          </div>

          <hr className="hr-wood mt-6" />

          <SectionTitle as="h2" align="left" subtitle="A few clues to get you started.">
            Initial evidence
          </SectionTitle>
          <EvidenceStrip evidence={initialEvidence} locations={ready.locations} />

          <div className="mt-6 flex flex-col gap-3">
            {ready.status === 'closed' ? (
              <ButtonLink to={`/game/${id}/debrief`} size="lg" block>
                This case is closed — read the debrief ▸
              </ButtonLink>
            ) : (
              <Button size="lg" block onClick={() => navigate(`/game/${id}`)}>
                Begin investigation ▸
              </Button>
            )}
            <p className="text-center ink-soft" style={{ margin: 0, fontSize: 13 }}>
              {ready.difficulty} difficulty · {ready.llm_mode === 'gemini' ? 'Live Gemini suspects' : 'Scripted suspects'} · the clock starts at {formatClock12(ready.clock)}
            </p>
          </div>
        </section>
      ) : null}
    </div>
  )
}

export default Briefing
