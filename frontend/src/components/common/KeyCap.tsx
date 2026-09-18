import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

/** A keyboard key badge: <KeyCap>`</KeyCap>, <KeyCap>Enter</KeyCap>. */
export function KeyCap({ children, className, title }: { children: ReactNode; className?: string; title?: string }) {
  return (
    <kbd className={cn('keycap', className)} title={title}>
      {children}
    </kbd>
  )
}

export default KeyCap
