/**
 * TypewriterProgress — the lacquer loading strip (DESIGN §5.1): typewriter icon, progress text that types in,
 * and a gold progress bar (indeterminate when `progress` is null).
 *
 *   <TypewriterProgress active lines={['Writing the cast…', 'Planting the evidence…']} progress={null} />
 */
import { useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/cn'
import { motionDisabled } from '@/lib/motion'

export interface TypewriterProgressProps {
  active: boolean
  /** progress lines in order; the last one is typed in */
  lines: string[]
  /** 0..1, or null/undefined for indeterminate */
  progress?: number | null
  className?: string
  /** how many earlier lines to keep visible above the current one */
  history?: number
}

function TypewriterIcon() {
  return (
    <svg className="typewriter-strip__icon" width="34" height="30" viewBox="0 0 34 30" aria-hidden="true" focusable="false">
      <rect x="4" y="12" width="26" height="12" rx="2" fill="#2c211a" stroke="currentColor" strokeWidth="1.5" />
      <rect x="8" y="6" width="18" height="7" rx="1.5" fill="#1b1410" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11" y="2" width="12" height="5" fill="#f3e7cb" />
      {[8, 12, 16, 20, 24].map((x) => (
        <circle key={x} cx={x + 1} cy="16" r="1.2" fill="currentColor" />
      ))}
      {[10, 14, 18, 22].map((x) => (
        <circle key={x} cx={x + 1} cy="19.5" r="1.2" fill="currentColor" />
      ))}
      <rect x="9" y="22" width="16" height="1.6" fill="currentColor" />
      <rect x="2" y="24" width="30" height="3" rx="1" fill="#2c211a" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  )
}

export function TypewriterProgress({ active, lines, progress, className, history = 2 }: TypewriterProgressProps) {
  const current = lines[lines.length - 1] ?? ''
  const previous = useMemo(() => lines.slice(Math.max(0, lines.length - 1 - history), Math.max(0, lines.length - 1)), [lines, history])
  const [typed, setTyped] = useState(current)

  useEffect(() => {
    if (motionDisabled() || !active) {
      setTyped(current)
      return
    }
    setTyped('')
    let i = 0
    const step = () => {
      i += 1
      setTyped(current.slice(0, i))
      if (i < current.length) timer = setTimeout(step, 22 + Math.random() * 30)
    }
    let timer = setTimeout(step, 40)
    return () => clearTimeout(timer)
  }, [current, active])

  const done = typed.length >= current.length
  const pct = typeof progress === 'number' ? Math.max(0, Math.min(1, progress)) : null

  return (
    <div className={cn('typewriter-strip', className)} aria-live="polite" aria-busy={active || undefined} data-active={active || undefined}>
      <TypewriterIcon />
      <div className="typewriter-strip__body">
        {previous.map((line, i) => (
          <div key={`${i}-${line}`} className="typewriter-strip__line muted" style={{ fontSize: 11 }}>
            {line}
          </div>
        ))}
        <div className={cn('typewriter-strip__line', active && !done && 'typing-cursor')}>{typed || (active ? ' ' : 'Ready.')}</div>
        <div className={cn('progress-bar', active && pct == null && 'progress-bar--indeterminate')} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct == null ? undefined : Math.round(pct * 100)} aria-label="Progress">
          <div className="progress-bar__fill" style={{ ['--progress' as string]: pct == null ? (active ? '30%' : '0%') : `${Math.round(pct * 100)}%` }} />
        </div>
      </div>
    </div>
  )
}

export default TypewriterProgress
