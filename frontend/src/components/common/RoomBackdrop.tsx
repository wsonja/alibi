/**
 * RoomBackdrop — full-screen painted plate behind every screen.
 * Prefers concept-board webps in /backdrops/ (responsive 16×9 / 21×9 / 9×16).
 * Investigation follows the selected suspect's last_seen location when known.
 */
import { useLocation } from 'react-router-dom'
import { backdropUrls, legacyArtForPath, sceneForLocation, sceneForPath, type BackdropScene } from '@/lib/backdrops'
import { selectPrimarySuspect, useGame } from '@/store/game'

/** @deprecated prefer sceneForPath — kept for callers/tests that keyed off art JPG names */
export function artForPath(pathname: string): string {
  return legacyArtForPath(pathname)
}

function sceneForApp(pathname: string, locationId: string | null | undefined): BackdropScene {
  if (pathname.startsWith('/game/') && !pathname.endsWith('/briefing') && !pathname.endsWith('/debrief')) {
    return sceneForLocation(locationId)
  }
  return sceneForPath(pathname)
}

export function RoomBackdrop() {
  const { pathname } = useLocation()
  const primary = useGame(selectPrimarySuspect)
  const locationId = primary?.last_seen_location ?? null
  const scene = sceneForApp(pathname, locationId)
  const urls = backdropUrls(scene)
  const isSetup = pathname === '/'

  return (
    <div className={`room-bg room-bg--art${isSetup ? ' room-bg--setup' : ''}`} aria-hidden="true" data-scene={scene}>
      <picture className="room-bg__picture">
        <source media="(orientation: portrait) and (max-width: 900px)" srcSet={urls.mobile} />
        <source media="(min-aspect-ratio: 2/1)" srcSet={urls.ultrawide} />
        <img className="room-bg__img" src={urls.landscape} alt="" draggable={false} />
      </picture>
      {!isSetup ? <div className="room-bg__dim" /> : <div className="room-bg__dim room-bg__dim--setup" />}
    </div>
  )
}

export default RoomBackdrop
