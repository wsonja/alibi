import { Link } from 'react-router-dom'
import { cn } from '@/lib/cn'

export const TAGLINE = 'New people. New lies. Every time.'

export interface MarqueeProps {
  /** 140px badge for the Investigation header */
  small?: boolean
  /** show the tagline under the logo (default true; never on small) */
  tagline?: boolean
  /** link target (default "/"); pass null for a static logo */
  to?: string | null
  className?: string
}

function Magnifier({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <circle cx="19" cy="19" r="13" fill="rgba(243,231,203,.35)" stroke="#C9A24B" strokeWidth="4" />
      <circle cx="19" cy="19" r="9" fill="rgba(216,35,42,.25)" />
      <path d="M14 13 Q19 9 24 13" stroke="rgba(255,255,255,.7)" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M29 29 L42 42" stroke="#5A331C" strokeWidth="8" strokeLinecap="round" />
      <path d="M29 29 L42 42" stroke="#C9A24B" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

/** The MURDER MYSTERY MAYHEM marquee (DESIGN §4). */
export function Marquee({ small, tagline = true, to = '/', className }: MarqueeProps) {
  const body = (
    <>
      <span className="marquee__l1">Murder Mystery</span>
      <span className="marquee__l2">Mayhem</span>
      {tagline && !small ? <span className="marquee__tag">{TAGLINE}</span> : null}
      <Magnifier className="marquee__glass" />
    </>
  )
  const cls = cn('marquee', small && 'marquee--small', className)
  if (to) {
    return (
      <Link to={to} className={cls} aria-label="Murder Mystery Mayhem — home">
        {body}
      </Link>
    )
  }
  return (
    <div className={cls} role="img" aria-label="Murder Mystery Mayhem">
      {body}
    </div>
  )
}

export default Marquee
