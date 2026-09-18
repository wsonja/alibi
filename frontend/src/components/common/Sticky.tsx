import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface StickyProps {
  children: ReactNode
  /** rotate the other way */
  right?: boolean
  className?: string
  style?: React.CSSProperties
}

/** Pale yellow sticky note in handwriting with a red push-pin. */
export function Sticky({ children, right, className, style }: StickyProps) {
  return (
    <div className={cn('sticky', right && 'sticky--right', className)} style={style} role="note">
      {children}
    </div>
  )
}

export default Sticky
