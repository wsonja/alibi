// placeholder — replaced by the Debrief+Judge+Archive lane
// Contract (INTERFACES §7): <JudgePanel gameId /> — renders only when GET /games/:id/debug returns 200 and useUI.judgeOpen.
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { DebugState } from '@/api/types'
import { KeyCap } from '@/components/common/KeyCap'
import { useUI } from '@/store/ui'

export interface JudgePanelProps {
  gameId: string
}

export function JudgePanel({ gameId }: JudgePanelProps) {
  const open = useUI((s) => s.judgeOpen)
  const setOpen = useUI((s) => s.setJudgeOpen)
  const [debug, setDebug] = useState<DebugState | null>(null)
  const [available, setAvailable] = useState<boolean | null>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    api
      .getDebugOrNull(gameId)
      .then((d) => {
        if (cancelled) return
        setDebug(d)
        setAvailable(d !== null)
      })
      .catch(() => {
        if (!cancelled) setAvailable(false)
      })
    return () => {
      cancelled = true
    }
  }, [gameId, open])

  if (!open || available === false) return null

  return (
    <div className="modal-backdrop" style={{ alignItems: 'start', overflow: 'auto' }}>
      <section className="lacquer lacquer--teal w-full max-w-5xl mt-6" aria-label="Judge / debug panel">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="display display--gold" style={{ fontSize: 14, margin: 0 }}>
            ⚙ Judge / Debug — demo &amp; development only · not for players
          </h2>
          <div className="flex items-center gap-2">
            <KeyCap>`</KeyCap>
            <KeyCap>F9</KeyCap>
            <span className="mono muted">toggle</span>
            <button type="button" className="toast__close" aria-label="Close judge panel" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>
        </div>
        {debug ? (
          <div className="mono mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(debug.suspects).map(([sid, s]) => (
              <div key={sid} className="lacquer lacquer--soft">
                <div className="display display--gold" style={{ fontSize: 11 }}>
                  {s.name}
                </div>
                <div>
                  pressure {s.stress} / {s.thresholds.join(' · ')}
                </div>
                <div>unlocked: {s.unlocked.join(', ') || '—'}</div>
                <div>revealed: {s.revealed.join(', ') || '—'}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mono muted">Loading private state…</p>
        )}
        <p className="mono muted mt-3" style={{ fontSize: 11 }}>
          Full panel (secrets, heard_log, outbox, context boxes) arrives with the Judge lane.
        </p>
      </section>
    </div>
  )
}

export default JudgePanel
