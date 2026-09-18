/**
 * ClockFace — SVG analog clock for the game clock ("HH:MM"). The hour hand moves with a transition.
 *
 *   <ClockFace time="00:15" size={64} />
 */
import { parseClock } from '@/lib/clock'
import { cn } from '@/lib/cn'

export interface ClockFaceProps {
  /** "HH:MM" (24 h) */
  time: string
  size?: number
  className?: string
  /** red accents (dawn is close) */
  dawn?: boolean
  title?: string
}

export function ClockFace({ time, size = 64, className, dawn, title }: ClockFaceProps) {
  const p = parseClock(time)
  const h = p ? p.hours % 12 : 0
  const m = p ? p.minutes : 0
  const hourAngle = (h + m / 60) * 30
  const minuteAngle = m * 6
  const label = title ?? (p ? `Clock showing ${time}` : 'Clock')
  const accent = dawn ? '#d8232a' : '#c9a24b'

  return (
    <svg className={cn('clock-face', className)} width={size} height={size} viewBox="0 0 100 100" role="img" aria-label={label}>
      <title>{label}</title>
      <circle cx="50" cy="50" r="47" fill="#f3e7cb" stroke="#7a4b22" strokeWidth="4" />
      <circle cx="50" cy="50" r="42" fill="none" stroke="#c9a24b" strokeWidth="1" />
      {Array.from({ length: 12 }, (_, i) => {
        const a = (i * 30 * Math.PI) / 180
        const r1 = i % 3 === 0 ? 33 : 37
        const x1 = 50 + r1 * Math.sin(a)
        const y1 = 50 - r1 * Math.cos(a)
        const x2 = 50 + 40 * Math.sin(a)
        const y2 = 50 - 40 * Math.cos(a)
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#2b1b12" strokeWidth={i % 3 === 0 ? 2.5 : 1.2} />
      })}
      <line className="clock-face__hand" x1="50" y1="50" x2="50" y2="26" stroke="#2b1b12" strokeWidth="4" strokeLinecap="round" style={{ transformOrigin: '50px 50px', transform: `rotate(${hourAngle}deg)` }} />
      <line className="clock-face__hand" x1="50" y1="50" x2="50" y2="16" stroke="#2b1b12" strokeWidth="2.5" strokeLinecap="round" style={{ transformOrigin: '50px 50px', transform: `rotate(${minuteAngle}deg)` }} />
      <circle cx="50" cy="50" r="3.5" fill={accent} stroke="#2b1b12" strokeWidth="1" />
    </svg>
  )
}

export default ClockFace
