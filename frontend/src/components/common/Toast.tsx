/**
 * Toaster — bottom-centre lacquer strips for ticker / world events / errors (DESIGN §7).
 * Reads `toasts` from the game store; add with `useGame.getState().addToast({kind, text})`.
 */
import { useEffect } from 'react'
import { cn } from '@/lib/cn'
import { useGame, type Toast as ToastModel } from '@/store/game'

function ToastItem({ toast }: { toast: ToastModel }) {
  const dismiss = useGame((s) => s.dismissToast)
  useEffect(() => {
    if (!toast.ttlMs) return
    const t = setTimeout(() => dismiss(toast.id), toast.ttlMs)
    return () => clearTimeout(t)
  }, [toast.id, toast.ttlMs, dismiss])

  return (
    <div className={cn('toast', `toast--${toast.kind}`)} role={toast.kind === 'error' ? 'alert' : 'status'}>
      <div className="toast__text">
        {toast.kicker ? <span className="toast__kicker">{toast.kicker}</span> : null}
        {toast.text}
      </div>
      {toast.action ? (
        <button
          type="button"
          className="btn btn-black btn--sm"
          onClick={() => {
            toast.action?.onClick()
            dismiss(toast.id)
          }}
        >
          {toast.action.label}
        </button>
      ) : null}
      <button type="button" className="toast__close" aria-label="Dismiss" onClick={() => dismiss(toast.id)}>
        ×
      </button>
    </div>
  )
}

export function Toaster() {
  const toasts = useGame((s) => s.toasts)
  if (!toasts.length) return null
  return (
    <div className="toaster" aria-live="polite">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  )
}

export { ToastItem as Toast }
export default Toaster
