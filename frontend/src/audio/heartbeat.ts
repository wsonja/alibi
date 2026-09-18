// placeholder — replaced by the sensors/voice lane (Howler loop; rate = 0.8 + 0.7·stress_pct/100; muted in low-sensory)
// Contract (docs/INTERFACES.md §7): setHeartbeat(stressPct, enabled).

let lastStress = 0
let lastEnabled = false

export function setHeartbeat(stressPct: number, enabled: boolean): void {
  lastStress = Math.max(0, Math.min(100, stressPct))
  lastEnabled = enabled
}

/** For debugging / the Judge panel: the last values passed to setHeartbeat. */
export function heartbeatState(): { stressPct: number; enabled: boolean } {
  return { stressPct: lastStress, enabled: lastEnabled }
}
