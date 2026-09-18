import type { ElementType, HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface PanelProps extends HTMLAttributes<HTMLElement> {
  /** parchment (cream paper, double border) or lacquer (near-black, gold border) */
  variant?: 'parchment' | 'lacquer'
  tight?: boolean
  flat?: boolean
  /** no corner flourishes (parchment only) */
  plain?: boolean
  /** teal text tint (lacquer only, judge panel) */
  teal?: boolean
  as?: ElementType
  children?: ReactNode
}

/** A physical panel on the desk: `.parchment` or `.lacquer`. */
export function Panel({ variant = 'parchment', tight, flat, plain, teal, as, className, children, ...rest }: PanelProps) {
  const Tag: ElementType = as ?? 'section'
  const cls =
    variant === 'parchment'
      ? cn('parchment', tight && 'parchment--tight', flat && 'parchment--flat', plain && 'parchment--plain', className)
      : cn('lacquer', flat && 'lacquer--soft', teal && 'lacquer--teal', className)
  return (
    <Tag className={cls} {...rest}>
      {children}
    </Tag>
  )
}

export default Panel
