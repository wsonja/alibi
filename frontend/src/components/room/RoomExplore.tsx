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

/**
 * Place each clue on a real surface for the painted plate behind it
 * (study→library, darkroom/corridor→bedroom, billiard→dining, garden→manor).
 * Keyed by evidence id so order never stacks two items on the same spot.
 */
type SpotLayout = { top: string; left: string; size: number }

const SPOT_PLACEMENT: Record<string, SpotLayout> = {
  // Study (library plate): desk right, grate left of the fire
  decanter: { top: '56%', left: '70%', size: 72 }, // desk surface by the lamp
  ledger: { top: '62%', left: '82%', size: 68 }, // open on the front of the desk
  solicitor_letter: { top: '68%', left: '64%', size: 54 }, // desk drawer edge
  ashes_in_grate: { top: '74%', left: '16%', size: 50 }, // hearth / grate

  // Darkroom (bedroom plate stand-in): shelf/desk ≠ floor
  cyanide_jar: { top: '36%', left: '20%', size: 56 }, // chemical shelf / side desk
  cigar_ash: { top: '84%', left: '58%', size: 46 }, // floor by the workbench / ottoman

  // Billiard room (dining plate stand-in): mantel / sideboard
  cigar_case: { top: '40%', left: '14%', size: 60 }, // left sideboard / mantel shelf

  // Garden (manor exterior stand-in): ground / fountain rim
  necklace_clasp: { top: '78%', left: '38%', size: 42 }, // on the wet ground by the drive

  // Servants' corridor (bedroom plate): floor by the door
  torn_reference: { top: '82%', left: '10%', size: 52 }, // paper on the floor near the doorway
}

const FALLBACK_SURFACES: SpotLayout[] = [
  { top: '72%', left: '30%', size: 56 }, // floor
  { top: '58%', left: '70%', size: 60 }, // table
  { top: '48%', left: '18%', size: 54 }, // shelf / side table
]

function layoutFor(evidenceId: string, index: number): SpotLayout {
  return SPOT_PLACEMENT[evidenceId] ?? FALLBACK_SURFACES[index % FALLBACK_SURFACES.length]!
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
