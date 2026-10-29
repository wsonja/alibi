/**
 * Full-screen room explorer: backdrop + unmistakable clickable clue spots.
 * Mystery spots are glowing glints (no spoiler art). Collected spots reveal the plate.
 */
import { useState } from 'react'
import type { ClueSpot, PublicEvidence, PublicLocation } from '@/api/types'
import { Button } from '@/components/common/Button'
import { EvidenceIcon } from '@/components/common/EvidenceIcon'
import { backdropUrls, sceneForLocation } from '@/lib/backdrops'
import { evidenceArtUrl } from '@/lib/briefingStory'
import { cn } from '@/lib/cn'

/** Per-location hotspot anchors (percent of stage). Extra spots fall back to EXTRA. */
const ROOM_LAYOUT: Record<string, Array<{ top: string; left: string }>> = {
  study: [
    { top: '62%', left: '58%' }, // desk — decanter
    { top: '55%', left: '72%' }, // drawer — letter
    { top: '48%', left: '40%' }, // desk surface — ledger
    { top: '78%', left: '28%' }, // grate — ashes
  ],
  darkroom: [
    { top: '42%', left: '68%' },
    { top: '72%', left: '45%' },
  ],
  billiard_room: [{ top: '48%', left: '55%' }],
  garden: [{ top: '68%', left: '50%' }],
  servants_corridor: [{ top: '58%', left: '42%' }],
  drawing_room: [],
}

const EXTRA: Array<{ top: string; left: string }> = [
  { top: '58%', left: '22%' },
  { top: '42%', left: '68%' },
  { top: '70%', left: '55%' },
  { top: '38%', left: '38%' },
]

function layoutFor(locationId: string, index: number): { top: string; left: string } {
  const room = ROOM_LAYOUT[locationId]
  if (room && room[index]) return room[index]!
  return EXTRA[index % EXTRA.length]!
}

export interface RoomExploreProps {
  location: PublicLocation
  caseId: string
  pending: boolean
  lastFound: PublicEvidence | null
  onCollect: (evidenceId: string) => Promise<void>
  onClose: () => void
  /** Other rooms that still have uncollected clues — shown when this room is empty. */
  otherClueRooms?: Array<{ id: string; name: string; remaining: number }>
  onGoToRoom?: (locationId: string) => void
}

export function RoomExplore({
  location,
  caseId,
  pending,
  lastFound,
  onCollect,
  onClose,
  otherClueRooms = [],
  onGoToRoom,
}: RoomExploreProps) {
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
            <p className="muted" style={{ margin: '4px 0 0', maxWidth: 520 }}>
              {spots.length === 0
                ? location.description
                : remaining > 0
                  ? `${remaining} glint${remaining === 1 ? '' : 's'} in this room — click each glowing spot to inspect it.`
                  : 'You have inspected everything here.'}
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
            disabled={pending || spot.collected}
            onCollect={onCollect}
          />
        ))}

        {spots.length === 0 ? (
          <div className="room-explore__empty">
            <p style={{ margin: '0 0 12px' }}>Nothing is hidden in this room.</p>
            {otherClueRooms.length > 0 ? (
              <div className="room-explore__elsewhere">
                <p className="muted" style={{ margin: '0 0 8px', fontSize: 14 }}>
                  Try a room with glints:
                </p>
                <div className="flex gap-2 flex-wrap" style={{ justifyContent: 'center' }}>
                  {otherClueRooms.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      className="chip chip--dark"
                      onClick={() => onGoToRoom?.(r.id)}
                    >
                      {r.name} · {r.remaining}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <footer className="room-explore__footer">
        <span className="mono" style={{ fontSize: 12 }}>
          {spots.length === 0
            ? 'No clues here'
            : remaining === 0
              ? 'All clues here collected.'
              : `${remaining} clue${remaining === 1 ? '' : 's'} left — look for the pulsing gold spots`}
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
  const mystery = !spot.label && !spot.collected
  const src = evidenceArtUrl(caseId, spot.id)
  const label = spot.collected
    ? spot.label ?? 'Collected'
    : spot.label ?? 'Something here…'

  return (
    <button
      type="button"
      className={cn(
        'room-spot',
        spot.collected && 'room-spot--done',
        mystery && 'room-spot--mystery',
        !mystery && !spot.collected && 'room-spot--known',
      )}
      style={{ top: layout.top, left: layout.left }}
      disabled={disabled}
      aria-label={spot.collected ? `${label} (already collected)` : `Inspect: ${label}`}
      onClick={() => void onCollect(spot.id)}
    >
      <span className="room-spot__ring" aria-hidden="true" />
      <span className="room-spot__art">
        {mystery ? (
          <span className="room-spot__glint" aria-hidden="true">
            ?
          </span>
        ) : imgOk ? (
          <img src={src} alt="" onError={() => setImgOk(false)} draggable={false} />
        ) : (
          <EvidenceIcon name={spot.label ?? spot.id} size={44} color="#f0d48a" />
        )}
      </span>
      <span className="room-spot__label">{mystery ? 'Inspect' : label}</span>
    </button>
  )
}

export default RoomExplore
