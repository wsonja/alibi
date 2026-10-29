/**
 * Full-screen room explorer: backdrop + evidence PNGs lying in the scene.
 * No glow rings, no counts — objects are as quiet as the art allows.
 */
import { useState } from 'react'
import type { ClueSpot, PublicEvidence, PublicLocation } from '@/api/types'
import { Button } from '@/components/common/Button'
import { EvidenceIcon } from '@/components/common/EvidenceIcon'
import { backdropUrls, sceneForLocation } from '@/lib/backdrops'
import { evidenceArtUrl } from '@/lib/briefingStory'
import { cn } from '@/lib/cn'

/** Per-location anchors (percent of stage). */
const ROOM_LAYOUT: Record<string, Array<{ top: string; left: string; size?: number }>> = {
  study: [
    { top: '64%', left: '56%', size: 78 },
    { top: '52%', left: '74%', size: 64 },
    { top: '46%', left: '38%', size: 70 },
    { top: '80%', left: '26%', size: 56 },
  ],
  darkroom: [
    { top: '40%', left: '70%', size: 68 },
    { top: '74%', left: '44%', size: 58 },
  ],
  billiard_room: [{ top: '50%', left: '54%', size: 72 }],
  garden: [{ top: '70%', left: '48%', size: 54 }],
  servants_corridor: [{ top: '60%', left: '40%', size: 62 }],
  drawing_room: [],
}

const EXTRA: Array<{ top: string; left: string; size?: number }> = [
  { top: '60%', left: '24%', size: 64 },
  { top: '44%', left: '66%', size: 60 },
  { top: '72%', left: '52%', size: 58 },
]

function layoutFor(locationId: string, index: number): { top: string; left: string; size: number } {
  const room = ROOM_LAYOUT[locationId]
  const hit = room?.[index] ?? EXTRA[index % EXTRA.length]!
  return { top: hit.top, left: hit.left, size: hit.size ?? 64 }
}

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
  const spots = (location.spots ?? []).filter((s) => !s.collected)

  return (
    <div className="room-explore" role="dialog" aria-modal="true" aria-label={`Exploring ${location.name}`}>
      <div className="room-explore__stage" style={{ backgroundImage: `url(${bg})` }}>
        <div className="room-explore__veil room-explore__veil--soft" />
        <header className="room-explore__header">
          <div>
            <p className="story-kicker" style={{ color: 'var(--gold-300)' }}>
              Searching
            </p>
            <h2 className="display display--gold" style={{ margin: 0, fontSize: 22 }}>
              {location.name}
            </h2>
            <p className="muted" style={{ margin: '4px 0 0', maxWidth: 480 }}>
              {location.description}
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
            layout={layoutFor(location.id, i)}
            disabled={pending}
            onCollect={onCollect}
          />
        ))}
      </div>

      <footer className="room-explore__footer">
        <span className="mono" style={{ fontSize: 12 }}>
          Look around. Click anything that seems out of place.
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
  layout: { top: string; left: string; size: number }
  disabled: boolean
  onCollect: (id: string) => Promise<void>
}) {
  const [imgOk, setImgOk] = useState(true)
  const src = evidenceArtUrl(caseId, spot.id)
  const name = spot.label ?? 'Something here'

  return (
    <button
      type="button"
      className={cn('room-spot', 'room-spot--object')}
      style={{ top: layout.top, left: layout.left, width: layout.size }}
      disabled={disabled}
      aria-label={`Inspect ${name}`}
      onClick={() => void onCollect(spot.id)}
    >
      <span className="room-spot__art" style={{ width: layout.size, height: layout.size }}>
        {imgOk ? (
          <img src={src} alt="" onError={() => setImgOk(false)} draggable={false} />
        ) : (
          <EvidenceIcon name={spot.label ?? spot.id} size={Math.round(layout.size * 0.45)} color="#c9a24b" />
        )}
      </span>
    </button>
  )
}

export default RoomExplore
