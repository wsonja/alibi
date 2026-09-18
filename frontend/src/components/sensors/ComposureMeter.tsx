// placeholder — replaced by the sensors lane
// Contract (INTERFACES §7): <ComposureMeter /> (no props). Shows the player's own composure label so the mechanic is legible.
import { composureLabel, useSensors } from '@/store/sensors'

export function ComposureMeter() {
  const enabled = useSensors((s) => s.enabled)
  const starting = useSensors((s) => s.starting)
  const composure = useSensors((s) => s.composure)
  const score = useSensors((s) => s.composureScore)
  const error = useSensors((s) => s.error)
  const pct = score == null ? 0 : Math.round((1 - Math.max(0, Math.min(1, score))) * 100)
  const label = !enabled ? (starting ? 'Starting camera…' : 'Camera off') : composure ? composureLabel(composure) : 'Calibrating…'

  return (
    <section className="lacquer lacquer--soft flex flex-col gap-2" aria-label="Composure meter">
      <div className="flex items-baseline justify-between">
        <span className="label-caps label-caps--gold">Composure</span>
        <span className="mono" style={{ fontSize: 12 }}>
          {label}
        </span>
      </div>
      <div className="pressure-bar" style={{ ['--pct' as string]: enabled ? pct : 0 }} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={enabled ? pct : undefined} aria-label="Nervousness" />
      <p className="muted" style={{ margin: 0, fontSize: 13, fontStyle: 'italic' }}>
        {error ? error : 'Staying composed reveals more.'}
      </p>
    </section>
  )
}

export default ComposureMeter
