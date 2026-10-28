/**
 * Briefing — guided story, not a fact sheet.
 * Chapters: what happened → victim → timeline (one beat per click/key) → meet each suspect → first evidence → Begin.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { PublicEvidence, PublicSuspect } from '@/api/types'
import { Button, ButtonLink } from '@/components/common/Button'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { EvidenceArt } from '@/components/common/EvidenceArt'
import { PaintedPortrait } from '@/components/portrait/PaintedPortrait'
import { cn } from '@/lib/cn'
import { backdropUrls } from '@/lib/backdrops'
import {
  advanceStory,
  claimedPlaceLabel,
  claimedSceneFor,
  evidenceLocationName,
  evidenceScene,
  initialEvidence,
  initialProgress,
  introLineFor,
  victimArtUrl,
  type StoryProgress,
} from '@/lib/briefingStory'
import { formatClock12 as fmt12 } from '@/lib/clock'
import { deriveDeathWindow } from '@/lib/text'
import { useGame } from '@/store/game'

function Hint({ children }: { children: string }) {
  return (
    <p className="story-hint" aria-hidden="true">
      {children}
    </p>
  )
}

function StoryShell({
  bg,
  children,
  onAdvance,
  canAdvance,
}: {
  bg: string
  children: React.ReactNode
  onAdvance: () => void
  canAdvance: boolean
}) {
  return (
    <div
      className="story-stage"
      style={{ backgroundImage: `url(${bg})` }}
      onClick={() => {
        if (canAdvance) onAdvance()
      }}
      role="presentation"
    >
      <div className="story-stage__veil" />
      <div className="story-stage__content">{children}</div>
      {canAdvance ? <Hint>Click or press any key to continue</Hint> : null}
    </div>
  )
}

function WhatChapter({ text }: { text: string }) {
  return (
    <article className="story-card fade-in">
      <p className="story-kicker">Tonight</p>
      <h1 className="story-title">What happened?</h1>
      <p className="story-body">{text}</p>
    </article>
  )
}

function VictimChapter({
  name,
  description,
  cause,
  deathLabel,
  clock,
  caseId,
}: {
  name: string
  description: string
  cause: string
  deathLabel: string | null
  clock: string
  caseId: string
}) {
  const [imgOk, setImgOk] = useState(true)
  const src = victimArtUrl(caseId)
  return (
    <article className="story-card story-card--victim fade-in">
      <p className="story-kicker">The study</p>
      <h1 className="story-title">The victim</h1>
      {imgOk ? (
        <figure className="story-victim-art">
          <img src={src} alt={`${name}, found dead in the study`} onError={() => setImgOk(false)} draggable={false} />
        </figure>
      ) : null}
      <h2 className="story-name">{name}</h2>
      <p className="story-body">{description}</p>
      <p className="story-body story-body--soft">{cause}</p>
      {deathLabel ? (
        <div className="story-time-chip pop-in" role="status">
          Time of death · between {deathLabel}
        </div>
      ) : (
        <div className="story-time-chip pop-in" role="status">
          Your clock · {fmt12(clock)}
        </div>
      )}
    </article>
  )
}

function TimelineChapter({
  entries,
  shown,
}: {
  entries: { time: string; event: string }[]
  shown: number
}) {
  return (
    <article className="story-card fade-in">
      <p className="story-kicker">As the house remembers it</p>
      <h1 className="story-title">Public timeline</h1>
      <ol className="story-timeline">
        {entries.slice(0, shown).map((t, i) => (
          <li key={`${t.time}-${i}`} className="story-timeline__item pop-in">
            <span className="story-timeline__time">{t.time}</span>
            <span className="story-timeline__event">{t.event}</span>
          </li>
        ))}
      </ol>
      {shown < entries.length ? (
        <p className="story-body story-body--soft" style={{ marginTop: 12 }}>
          {entries.length - shown} more beat{entries.length - shown === 1 ? '' : 's'}…
        </p>
      ) : null}
    </article>
  )
}

function MeetChapter({ suspect, caseId }: { suspect: PublicSuspect; caseId: string }) {
  return (
    <article className="story-card story-card--meet fade-in">
      <p className="story-kicker">{claimedPlaceLabel(suspect.id)}</p>
      <h1 className="story-title">A face in the house</h1>
      <div className="story-meet">
        <PaintedPortrait suspect={suspect} emotion={suspect.emotion} size={160} caseId={caseId} />
        <div>
          <h2 className="story-name">{suspect.name}</h2>
          <p className="story-role">{suspect.role}</p>
          <p className="story-speech">“{introLineFor(suspect)}”</p>
        </div>
      </div>
    </article>
  )
}

function EvidenceChapter({
  item,
  caseId,
  locationName,
}: {
  item: PublicEvidence
  caseId: string
  locationName: string
}) {
  return (
    <article className="story-card fade-in">
      <p className="story-kicker">Found in {locationName}</p>
      <h1 className="story-title">First evidence</h1>
      <div className="story-evidence">
        <EvidenceArt
          className="story-evidence__art"
          caseId={caseId}
          evidenceId={item.id}
          name={item.name}
          description={item.description}
          size={160}
          fit="contain"
          iconColor="#7a4b22"
        />
        <div>
          <h2 className="story-name">{item.name}</h2>
          <p className="story-body">{item.description}</p>
          <p className="story-body story-body--soft">You may examine it properly once the investigation begins.</p>
        </div>
      </div>
    </article>
  )
}

function ReadyChapter({
  onBegin,
  closed,
  debriefPath,
}: {
  onBegin: () => void
  closed: boolean
  debriefPath: string
}) {
  return (
    <article className="story-card fade-in" style={{ textAlign: 'center' }}>
      <p className="story-kicker">Until dawn</p>
      <h1 className="story-title">The house is waiting</h1>
      <p className="story-body">You have the story the house will admit to. The rest you must dig for.</p>
      {closed ? (
        <ButtonLink to={debriefPath} size="lg">
          This case is closed — read the debrief ▸
        </ButtonLink>
      ) : (
        <Button
          size="lg"
          onClick={(e) => {
            e.stopPropagation()
            onBegin()
          }}
        >
          Begin investigation ▸
        </Button>
      )}
    </article>
  )
}

export function Briefing() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const game = useGame((s) => s.game)
  const loading = useGame((s) => s.loading)
  const error = useGame((s) => s.error)
  const loadGame = useGame((s) => s.loadGame)
  const [progress, setProgress] = useState<StoryProgress>(initialProgress)

  useEffect(() => {
    if (id) void loadGame(id)
  }, [id, loadGame])

  const ready = game && game.game_id === id ? game : null
  const death = useMemo(
    () => (ready ? deriveDeathWindow(ready.case.timeline_public, ready.case.victim.cause_of_death_public) : null),
    [ready],
  )
  const known = useMemo(() => (ready ? initialEvidence(ready.evidence) : []), [ready])
  const firstEvidence = known[0] ?? null

  const advance = useCallback(() => {
    if (!ready) return
    setProgress((p) => advanceStory(p, ready.case.timeline_public, ready.cast.length))
  }, [ready])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (progress.chapter === 'ready') return
      e.preventDefault()
      advance()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [advance, progress.chapter])

  if (!ready && loading) {
    return (
      <div className="screen screen--briefing">
        <div className="story-card mono muted" style={{ margin: '40px auto', maxWidth: 420, textAlign: 'center' }} aria-busy="true">
          Opening the case file…
        </div>
      </div>
    )
  }
  if (!ready && !loading && error) {
    return (
      <div className="screen screen--briefing">
        <div style={{ maxWidth: 640, margin: '40px auto' }}>
          <ErrorNotice message={error} onRetry={() => void loadGame(id)} />
        </div>
      </div>
    )
  }
  if (!ready) return null

  const caseId = ready.case.id
  let bg = backdropUrls('library').landscape
  if (progress.chapter === 'victim') bg = backdropUrls('library').landscape
  if (progress.chapter === 'meet') {
    const s = ready.cast[progress.meetIndex]
    if (s) bg = backdropUrls(claimedSceneFor(s.id)).landscape
  }
  if ((progress.chapter === 'evidence' || progress.chapter === 'ready') && firstEvidence) {
    bg = backdropUrls(evidenceScene(firstEvidence, ready.locations)).landscape
  }
  if (progress.chapter === 'what') bg = backdropUrls('manor_exterior').landscape

  const canAdvance = progress.chapter !== 'ready'

  return (
    <div className="screen screen--story">
      <StoryShell bg={bg} onAdvance={advance} canAdvance={canAdvance}>
        {progress.chapter === 'what' ? <WhatChapter text={ready.case.briefing} /> : null}
        {progress.chapter === 'victim' ? (
          <VictimChapter
            name={ready.case.victim.name}
            description={ready.case.victim.description}
            cause={ready.case.victim.cause_of_death_public}
            deathLabel={death?.label ?? null}
            clock={ready.clock}
            caseId={caseId}
          />
        ) : null}
        {progress.chapter === 'timeline' ? (
          <TimelineChapter entries={ready.case.timeline_public} shown={progress.timelineShown} />
        ) : null}
        {progress.chapter === 'meet' && ready.cast[progress.meetIndex] ? (
          <MeetChapter suspect={ready.cast[progress.meetIndex]!} caseId={caseId} />
        ) : null}
        {progress.chapter === 'evidence' && firstEvidence ? (
          <EvidenceChapter
            item={firstEvidence}
            caseId={caseId}
            locationName={evidenceLocationName(firstEvidence, ready.locations)}
          />
        ) : null}
        {progress.chapter === 'evidence' && !firstEvidence ? (
          <article className="story-card fade-in">
            <h1 className="story-title">No evidence yet</h1>
            <p className="story-body">Search the rooms once the investigation begins.</p>
            <Button size="lg" onClick={() => setProgress((p) => ({ ...p, chapter: 'ready' }))}>
              Continue
            </Button>
          </article>
        ) : null}
        {progress.chapter === 'ready' ? (
          <ReadyChapter
            closed={ready.status === 'closed'}
            debriefPath={`/game/${id}/debrief`}
            onBegin={() => navigate(`/game/${id}`)}
          />
        ) : null}
      </StoryShell>
      <div className="story-progress" aria-hidden="true">
        {(['what', 'victim', 'timeline', 'meet', 'evidence', 'ready'] as const).map((c) => (
          <span key={c} className={cn('story-progress__dot', progress.chapter === c && 'is-active')} />
        ))}
      </div>
    </div>
  )
}

export default Briefing
