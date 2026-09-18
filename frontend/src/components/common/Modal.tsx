/**
 * Modal — accessible dialog: focus trap, Esc to close, backdrop click, scroll lock, focus restore.
 *
 *   <Modal open={open} onClose={close} title="Paste a Gemini key">…</Modal>
 */
import { useEffect, useId, useRef, type MouseEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/cn'

export interface ModalProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children: ReactNode
  /** parchment (default) or lacquer surface */
  variant?: 'parchment' | 'lacquer'
  /** max width in px (default 560) */
  width?: number
  className?: string
  /** Hide the × button (e.g. for blocking dialogs). Esc still works unless `disableEscape`. */
  hideClose?: boolean
  disableEscape?: boolean
  /** aria-describedby target id */
  describedBy?: string
  /** Element to focus on open; defaults to the first focusable control, then the panel. */
  initialFocus?: React.RefObject<HTMLElement | null>
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function Modal({ open, onClose, title, children, variant = 'parchment', width = 560, className, hideClose, disableEscape, describedBy, initialFocus }: ModalProps) {
  const panelRef = useRef<HTMLDivElement | null>(null)
  const previouslyFocused = useRef<Element | null>(null)
  const titleId = useId()

  useEffect(() => {
    if (!open) return
    previouslyFocused.current = document.activeElement
    const panel = panelRef.current
    const target = initialFocus?.current ?? panel?.querySelector<HTMLElement>(FOCUSABLE) ?? panel
    const raf = requestAnimationFrame(() => target?.focus({ preventScroll: true }))
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !disableEscape) {
        e.stopPropagation()
        onClose()
        return
      }
      if (e.key !== 'Tab' || !panel) return
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((n) => n.offsetParent !== null || n === document.activeElement)
      if (nodes.length === 0) {
        e.preventDefault()
        panel.focus()
        return
      }
      const first = nodes[0]!
      const last = nodes[nodes.length - 1]!
      const active = document.activeElement
      if (e.shiftKey && (active === first || !panel.contains(active))) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && (active === last || !panel.contains(active))) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    return () => {
      cancelAnimationFrame(raf)
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = prevOverflow
      const prev = previouslyFocused.current
      if (prev instanceof HTMLElement) prev.focus({ preventScroll: true })
    }
  }, [open, onClose, disableEscape, initialFocus])

  if (!open || typeof document === 'undefined') return null

  const onBackdrop = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose()
  }

  return createPortal(
    <div className="modal-backdrop" onMouseDown={onBackdrop} data-testid="modal-backdrop">
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={describedBy}
        tabIndex={-1}
        className={cn('modal', variant === 'parchment' ? 'parchment' : 'lacquer', className)}
        style={{ ['--modal-w' as string]: `${width}px` }}
      >
        <div className="flex items-start justify-between gap-4">
          {title ? (
            <h2 id={titleId} className={cn('modal__title display', variant === 'parchment' ? 'ink' : 'display--gold')} style={{ fontSize: 15 }}>
              {title}
            </h2>
          ) : (
            <span />
          )}
          {!hideClose && (
            <button type="button" onClick={onClose} aria-label="Close dialog" className={cn('text-2xl leading-none px-1 -mt-1 cursor-pointer', variant === 'parchment' ? 'ink-soft hover:text-[var(--ink)]' : 'muted hover:text-[var(--paper-100)]')}>
              ×
            </button>
          )}
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}

export default Modal
