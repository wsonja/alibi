import { Button } from './Button'

export interface ErrorNoticeProps {
  message: string
  onRetry?: () => void
  retryLabel?: string
  hint?: string
}

/** Lacquer strip with a message and a retry button (used when the backend is unreachable). */
export function ErrorNotice({ message, onRetry, retryLabel = 'Try again', hint }: ErrorNoticeProps) {
  return (
    <div className="lacquer flex flex-wrap items-center gap-3" role="alert" style={{ borderLeftWidth: 6, borderLeftColor: 'var(--lie)' }}>
      <div className="flex-1 min-w-[200px]">
        <span className="toast__kicker">Something is wrong</span>
        <div>{message}</div>
        {hint ? (
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
            {hint}
          </div>
        ) : null}
      </div>
      {onRetry ? (
        <Button variant="black" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  )
}

export default ErrorNotice
