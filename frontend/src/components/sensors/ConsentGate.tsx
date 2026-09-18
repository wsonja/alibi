// placeholder — replaced by the sensors lane
// Contract (INTERFACES §7): <ConsentGate checked onChange /> — the camera consent checkbox with the privacy line.
import { useId } from 'react'

export interface ConsentGateProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

export const CONSENT_LINE = 'Suspects will read your expression. Video never leaves your device.'

export function ConsentGate({ checked, onChange, disabled, className }: ConsentGateProps) {
  const id = useId()
  return (
    <label htmlFor={id} className={`flex items-start gap-3 cursor-pointer ${className ?? ''}`}>
      <input id={id} type="checkbox" className="checkbox mt-1" checked={checked} onChange={(e) => onChange(e.target.checked)} disabled={disabled} aria-describedby={`${id}-desc`} />
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
  )
}

export default ConsentGate
