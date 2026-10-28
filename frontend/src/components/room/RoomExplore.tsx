/**
 * Full-screen room explorer: backdrop + clickable clue spots.
 * Collecting a spot calls search(location, evidenceId). PNGs optional at /evidence/{pack}/{id}.webp.
 */
import { useState } from 'react'
import type { ClueSpot, PublicEvidence, PublicLocation } from '@/api/types'
import { Button } from '@/components/common/Button'
import { EvidenceIcon } from '@/components/common/EvidenceIcon'
import { backdropUrls, sceneForLocation } from '@/lib/backdrops'
import { evidenceArtUrl } from '@/lib/briefingStory'
import { cn } from '@/lib/cn'

/** Stable layout positions so spots feel placed in the room (not a list). */
const SPOT_LAYOUT: Array<{ top: string; left: string }> = [
  { top: '58%', left: '22%' },
  { top: '42%', left: '68%' },
  { top: '70%', left: '55%' },
  { top: '38%', left: '38%' },
  { top: '62%', left: '78%' },
  { top: '48%', left: '12%' },
]

export interface RoomExploreProps {
  location: PublicLocation
  caseId: string
  pending: boolean
  lastFound: PublicEvidence | null
  onCollect: (evidenceId: string) => Promise<void>
  onClose: () => void
}

export function RoomExplore({ location, caseId, pending, lastFound, onCollect, onClose }: RoomExploreProps) {
  const bg = backdropUrls(sceneForLocation(location.id)).landscape
  const spots = location.spots ?? []
  const remaining = spots.filter((s) => !s.collected).length

  return (
    <div className="room-explore" role="dialog" aria-modal="true" aria-label={`Exploring ${location.name}`}>
      <div className="room-explore__stage" style={{ backgroundImage: `url(${bg})` }}>
        <div className="room-explore__veil" />
        <header className="room-explore__header">
          <div>
            <p className="story-kicker" style={{ color: 'var(--gold-300)' }}>
              Searching
            </p>
            <h2 className="display display--gold" style={{ margin: 0, fontSize: 22 }}>
              {location.name}
            </h2>
            <p className="muted" style={{ margin: '4px 0 0', maxWidth: 480 }}>
              {location.description} Click anything that catches your eye.
            </p>
          </div>
          <Button variant="black" size="sm" onClick={onClose}>
            Leave room
          </Button>
        </header>

        {spots.map((spot, i) => (
          <SpotButton
            key={spot.id}
            spot={spot}
            caseId={caseId}
            layout={SPOT_LAYOUT[i % SPOT_LAYOUT.length]!}
            disabled={pending || spot.collected}
            onCollect={onCollect}
          />
        ))}

        {spots.length === 0 ? (
          <p className="room-explore__empty">Nothing catches your eye here.</p>
        ) : null}
      </div>

      <footer className="room-explore__footer">
        <span className="mono" style={{ fontSize: 12 }}>
          {remaining === 0 ? 'All clues here collected.' : `${remaining} clue${remaining === 1 ? '' : 's'} left to inspect`}
        </span>
        {lastFound ? (
          <span className="room-explore__found pop-in">
            Added to evidence: <strong>{lastFound.name}</strong>
          </span>
        ) : null}
      </footer>
    </div>
  )
}

function SpotButton({
  spot,
  caseId,
  layout,
  disabled,
  onCollect,
}: {
  spot: ClueSpot
  caseId: string
  layout: { top: string; left: string }
  disabled: boolean
  onCollect: (id: string) => Promise<void>
}) {
  const [imgOk, setImgOk] = useState(true)
  const src = evidenceArtUrl(caseId, spot.id)
  const label = spot.collected ? spot.label ?? 'Collected' : spot.label ?? 'Something here…'

  return (
    <button
      type="button"
      className={cn('room-spot', spot.collected && 'room-spot--done', !spot.label && !spot.collected && 'room-spot--mystery')}
      style={{ top: layout.top, left: layout.left }}
      disabled={disabled}
      aria-label={spot.collected ? `${label} (already collected)` : `Inspect: ${label}`}
      onClick={() => void onCollect(spot.id)}
    >
      <span className="room-spot__art">
        {imgOk ? (
          <img src={src} alt="" onError={() => setImgOk(false)} draggable={false} />
        ) : (
          <EvidenceIcon name={spot.label ?? spot.id} size={40} color="#f0d48a" />
        )}
      </span>
      <span className="room-spot__label">{label}</span>
    </button>
  )
}

export default RoomExplore
