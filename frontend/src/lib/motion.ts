/** Motion preferences: OS reduced-motion OR the game's low-sensory mode. */

export function prefersReducedMotion(): boolean {
  try {
    return typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

export function lowSensoryActive(): boolean {
  try {
    return typeof document !== 'undefined' && document.documentElement.hasAttribute('data-low-sensory')
  } catch {
    return false
  }
}

/** True when nothing should animate (typing effects, blinks, heartbeat…). */
export function motionDisabled(): boolean {
  return prefersReducedMotion() || lowSensoryActive()
}
