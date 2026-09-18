import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface SectionTitleProps {
  children: ReactNode
  /** grey caps subtitle on the right, e.g. "FOUR PEOPLE. FOUR VERSIONS." */
  subtitle?: ReactNode
  as?: 'h1' | 'h2' | 'h3' | 'h4'
  /** gold text for use on lacquer */
  dark?: boolean
  align?: 'center' | 'left'
  className?: string
  id?: string
}

/** `—◆— THE SUSPECTS —◆—` with an optional right-hand subtitle. */
export function SectionTitle({ children, subtitle, as = 'h2', dark, align = 'center', className, id }: SectionTitleProps) {
  const Tag = as
  return (
    <div className={cn('section-title', dark && 'section-title--dark', align === 'left' && 'section-title--left', className)}>
      <Tag id={id} className="section-title__text">
        {children}
      </Tag>
      {subtitle ? <span className="section-title__sub">{subtitle}</span> : null}
    </div>
  )
}

export default SectionTitle
