/**
 * Concept-board room plates under `frontend/public/backdrops/` (docs/art-direction/vane_hall/).
 * Responsive triplets: landscape 16×9 (default), ultrawide 21×9, mobile 9×16.
 */

export type BackdropScene = 'manor_exterior' | 'library' | 'dining_room' | 'bedroom'

/** Vane Hall location id → nearest painted scene. */
export const LOCATION_SCENE: Record<string, BackdropScene> = {
  study: 'library',
  drawing_room: 'dining_room',
  billiard_room: 'dining_room',
  garden: 'manor_exterior',
  darkroom: 'bedroom',
  servants_corridor: 'bedroom',
}

export function sceneForLocation(locationId: string | null | undefined): BackdropScene {
  if (!locationId) return 'library'
  return LOCATION_SCENE[locationId] ?? 'library'
}

/** Route → default scene when no location is selected. */
export function sceneForPath(pathname: string): BackdropScene {
  if (pathname === '/' || pathname.startsWith('/archive')) return 'manor_exterior'
  if (pathname.endsWith('/briefing')) return 'library'
  if (pathname.endsWith('/debrief')) return 'library'
  if (pathname.startsWith('/game/')) return 'library'
  return 'manor_exterior'
}

export function backdropUrls(scene: BackdropScene): {
  landscape: string
  ultrawide: string
  mobile: string
  original: string
} {
  return {
    // PNG = source fidelity from the concept pack (the bundled .webp was over-compressed).
    landscape: `/backdrops/landscape_16x9/${scene}.png`,
    ultrawide: `/backdrops/ultrawide_21x9/${scene}.webp`,
    mobile: `/backdrops/mobile_9x16/${scene}.webp`,
    original: `/backdrops/scene_originals/${scene}.webp`,
  }
}

/** Legacy mockup JPG under /art/ — used only if a pack scene is unavailable. */
export function legacyArtForPath(pathname: string): string {
  if (pathname === '/') return 'setup'
  if (pathname.startsWith('/archive')) return 'archive'
  if (pathname.endsWith('/briefing')) return 'briefing'
  if (pathname.endsWith('/debrief')) return 'debrief'
  if (pathname.startsWith('/game/')) return 'investigation'
  return 'setup'
}
