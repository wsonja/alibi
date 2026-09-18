// Contract (INTERFACES §7): <JudgePanel gameId /> — renders only when GET /games/:id/debug returns 200 and useUI.judgeOpen.
// Toggle with the backtick key (wired in Investigation) or F9. Demo/dev only — not shown to players.
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { DebugState, DebugSuspect } from '@/api/types'
import { KeyCap } from '@/components/common/KeyCap'
import { cn } from '@/lib/cn'
import { useUI } from '@/store/ui'

export interface JudgePanelProps {
  gameId: string
}

function SuspectColumn({ id, s }: { id: string; s: DebugSuspect }) {
  const [showContext, setShowContext] = useState(false)
  const thresholds = s.thresholds ?? []
  return (
    <div className="lacquer lacquer--teal lacquer--soft flex flex-col gap-2" style={{ minWidth: 220 }}>
      <div className="display display--gold" style={{ fontSize: 12 }}>
        {s.name} <span className="muted mono" style={{ fontSize: 10 }}>({id})</span>
      </div>
      <div className="mono" style={{ fontSize: 12 }}>
        pressure <strong>{s.stress}</strong> / {thresholds.join(' · ')}
        <div className="pressure-bar mt-1" style={{ ['--pct' as string]: s.stress }} />
      </div>
      <div className="mono" style={{ fontSize: 11 }}>
        emotion: {s.emotion} · last honesty: {s.last_honesty || '—'} · silenced_until: {s.silenced_until ?? '—'}
      </div>

      <div>
        <div className="label-caps" style={{ fontSize: 10 }}>
          Secrets
        </div>
        <ul className="mono list-none p-0 m-0" style={{ fontSize: 11 }}>
          {s.secrets.map((sec) => (
            <li key={sec.id} title={sec.text}>
              {sec.status === 'revealed' ? '💬' : sec.status === 'unlocked' ? '🔓' : '🔒'} tier{sec.tier} {sec.id}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <div className="label-caps" style={{ fontSize: 10 }}>
          heard[] ({s.heard_log.length})
        </div>
        <ul className="mono list-none p-0 m-0" style={{ fontSize: 10, maxHeight: 80, overflowY: 'auto' }}>
          {s.heard_log.map((h, i) => (
            <li key={i}>
              (turn {h.turn}, from {h.from}, {h.channel}) {h.text}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <div className="label-caps" style={{ fontSize: 10 }}>
          outbox ({s.outbox.length})
        </div>
        <ul className="mono list-none p-0 m-0" style={{ fontSize: 10 }}>
          {s.outbox.map((o, i) => (
            <li key={i}>
              → {o.to} (turn {o.queued_turn}): {o.text}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <div className="label-caps" style={{ fontSize: 10 }}>
          last internal reasoning
        </div>
        <p className="mono" style={{ fontSize: 11, fontStyle: 'italic', whiteSpace: 'pre-wrap', margin: '2px 0' }}>
          {s.last_internal_reasoning || '—'}
        </p>
      </div>

      <button type="button" className="btn btn-black btn--sm" onClick={() => setShowContext((v) => !v)} aria-expanded={showContext}>
        {showContext ? 'Hide context' : 'Show context'}
      </button>
      {showContext ? (
        <pre className="mono" style={{ fontSize: 10, maxHeight: 160, overflow: 'auto', whiteSpace: 'pre-wrap', background: '#0d0906', padding: 6, border: '1px solid #5a3a1a', borderRadius: 4 }}>
          {(s.system_blocks ?? []).join('\n\n---\n\n') || '(no context captured yet)'}
        </pre>
      ) : null}
    </div>
  )
}

export function JudgePanel({ gameId }: JudgePanelProps) {
  const open = useUI((s) => s.judgeOpen)
  const setOpen = useUI((s) => s.setJudgeOpen)
  const [debug, setDebug] = useState<DebugState | null>(null)
  const [available, setAvailable] = useState<boolean | null>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    let timer: ReturnType<typeof setInterval> | null = null
    const load = () => {
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
    }
    load()
    timer = setInterval(load, 3000)
    return () => {
      cancelled = true
      if (timer) clearInterval(timer)
    }
  }, [gameId, open])

  if (!open || available === false) return null

  const crossClean = (debug?.cross_contamination.length ?? 0) === 0

  return (
    <div className="modal-backdrop" style={{ alignItems: 'start', overflow: 'auto', zIndex: 300 }}>
      <section className="lacquer lacquer--teal w-full max-w-6xl mt-6" aria-label="Judge / debug panel">
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
          <>
            <div className="mono muted mt-2" style={{ fontSize: 11 }}>
              llm_mode {debug.llm_mode} · turn {debug.turn} · clock {debug.clock} ·{' '}
              <span className={cn(crossClean ? '' : 'gold')} style={{ color: crossClean ? 'var(--truth)' : 'var(--lie)' }}>
                {crossClean ? '✓ No cross-contamination detected' : `⚠ ${debug.cross_contamination.length} cross-contamination hit(s)`}
              </span>
            </div>
            <div className="flex gap-3 mt-3 scroll-x pb-2">
              {Object.entries(debug.suspects).map(([sid, s]) => (
                <SuspectColumn key={sid} id={sid} s={s} />
              ))}
            </div>
            {debug.guard_events.length ? (
              <div className="mt-3">
                <div className="label-caps" style={{ fontSize: 10 }}>
                  Event log (most recent)
                </div>
                <ul className="mono list-none p-0 m-0" style={{ fontSize: 11, maxHeight: 100, overflowY: 'auto' }}>
                  {debug.guard_events
                    .slice(-20)
                    .reverse()
                    .map((g, i) => (
                      <li key={i}>
                        {g.kind}
                        {g.suspect_id ? ` (${g.suspect_id})` : ''}
                        {g.turn != null ? ` turn ${g.turn}` : ''}
                      </li>
                    ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : (
          <p className="mono muted">Loading private state…</p>
        )}
      </section>
    </div>
  )
}

export default JudgePanel
