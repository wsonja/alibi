import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/cn'

export interface PlacardProps {
  children: ReactNode
  /** internal route → renders a <Link> */
  to?: string
  /** external href → renders an <a> */
  href?: string
  onClick?: ButtonHTMLAttributes<HTMLButtonElement>['onClick']
  className?: string
  /** allow wrapping for long quotes */
  wide?: boolean
  title?: string
  'aria-label'?: string
}

/** Small brass wall plaque with gold serif caps: "PEOPLE LIE. DETAILS DON'T." */
export function Placard({ children, to, href, onClick, className, wide, title, ...aria }: PlacardProps) {
  const cls = cn('placard', wide && 'placard--wide', className)
  if (to) {
    return (
      <Link to={to} className={cls} title={title} {...aria}>
        {children}
      </Link>
    )
  }
  if (href) {
    return (
      <a href={href} className={cls} title={title} target="_blank" rel="noreferrer" {...aria}>
        {children}
      </a>
    )
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cls} title={title} {...aria}>
        {children}
      </button>
    )
  }
  return (
    <span className={cls} title={title} {...aria}>
      {children}
    </span>
  )
}

export default Placard
