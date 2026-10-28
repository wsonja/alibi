/**
 * Camera consent checkbox (INTERFACES §7). Checking it requests the webcam immediately
 * so the player sees a real browser prompt — not a silent no-op.
 */
import { useId, useState } from 'react'
import { useSensors } from '@/store/sensors'

export interface ConsentGateProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

export const CONSENT_LINE = 'Suspects will read your expression. Video never leaves your device.'

export function ConsentGate({ checked, onChange, disabled, className }: ConsentGateProps) {
  const id = useId()
  const start = useSensors((s) => s.start)
  const stop = useSensors((s) => s.stop)
  const enabled = useSensors((s) => s.enabled)
  const starting = useSensors((s) => s.starting)
  const error = useSensors((s) => s.error)
  const [busy, setBusy] = useState(false)

  async function handleChange(next: boolean) {
    onChange(next)
    if (!next) {
      stop()
      return
    }
    setBusy(true)
    try {
      await start()
    } finally {
      setBusy(false)
    }
  }

  const status = !checked
    ? 'Camera off.'
    : starting || busy
      ? 'Asking for camera permission…'
      : enabled
        ? 'Camera on — composure will update during the investigation.'
        : error
          ? error
          : 'Waiting for camera…'

  return (
    <div className={className}>
      <label htmlFor={id} className="flex items-start gap-3 cursor-pointer">
        <input
          id={id}
          type="checkbox"
          className="checkbox mt-1"
          checked={checked}
          onChange={(e) => void handleChange(e.target.checked)}
          disabled={disabled || busy || starting}
          aria-describedby={`${id}-desc`}
        />
        <span>
          <span className="ink" style={{ fontSize: 17 }}>
            <span aria-hidden="true">📷 </span>
            <strong>{CONSENT_LINE}</strong>
          </span>
          <span id={`${id}-desc`} className="ink-soft block" style={{ fontSize: 13 }}>
            Composure and gaze are computed in your browser from the webcam. No frame is uploaded or stored. You can switch it off at any time.
          </span>
        </span>
      </label>
      <p className="ink-soft" style={{ margin: '8px 0 0 28px', fontSize: 13 }} role="status" aria-live="polite">
        {status}
      </p>
    </div>
  )
}

export default ConsentGate
