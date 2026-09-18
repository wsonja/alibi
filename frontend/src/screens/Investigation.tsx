// placeholder — replaced by the Investigation lane
// Route /game/:id. Keeps the game loaded + socket connected so the store contract can be exercised now.
import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ButtonLink } from '@/components/common/Button'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { Marquee } from '@/components/common/Marquee'
import { PixelPortrait } from '@/components/portrait/PixelPortrait'
import { useGame } from '@/store/game'

export function Investigation() {
  const { id = '' } = useParams()
  const game = useGame((s) => s.game)
  const loading = useGame((s) => s.loading)
  const error = useGame((s) => s.error)
  const loadGame = useGame((s) => s.loadGame)
  const select = useGame((s) => s.select)
  const selection = useGame((s) => s.selection)

  useEffect(() => {
    if (id) void loadGame(id)
  }, [id, loadGame])

  return (
    <div className="screen screen--wide">
      <header className="flex items-center justify-between gap-4 flex-wrap">
        <Marquee small />
        <h1 className="display display--gold" style={{ fontSize: 20, margin: 0 }}>
          Investigation
        </h1>
        <span className="subtle-caps" style={{ color: 'rgba(243,231,203,.6)' }}>
          Question • Explore • Connect • Uncover
        </span>
      </header>
      <section className="lacquer mt-4">
        {loading && !game ? <p className="mono muted">Loading the room…</p> : null}
        {error && !game ? <ErrorNotice message={error} onRetry={() => void loadGame(id)} /> : null}
        {game ? (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              <em>{game.case.title}</em> · turn {game.turn} · {game.clock} · This screen is a placeholder; the Investigation lane replaces it.
            </p>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 list-none p-0 m-0">
              {game.cast.map((s) => (
                <li key={s.id}>
                  <button type="button" className={`suspect-card ${selection.primary === s.id ? 'selected' : ''} ${selection.secondary === s.id ? 'secondary' : ''}`} onClick={(e) => select(s.id, e.shiftKey)} aria-pressed={selection.primary === s.id}>
                    <PixelPortrait suspect={s} emotion={s.emotion} size={56} />
                    <span className="flex-1 min-w-0">
                      <span className="suspect-card__name block truncate">{s.name}</span>
                      <span className="suspect-card__meta block truncate">{s.role}</span>
                      <span className="pressure-label block mt-1">Pressure</span>
                      <span className="pressure-bar block" style={{ ['--pct' as string]: s.stress_pct }} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex gap-3 mt-4 flex-wrap">
              <ButtonLink to={`/game/${id}/briefing`} variant="black">
                ◀ Briefing
              </ButtonLink>
              {game.status === 'closed' ? <ButtonLink to={`/game/${id}/debrief`}>Debrief ▸</ButtonLink> : null}
              <Link to="/" className="placard">
                New case
              </Link>
            </div>
          </>
        ) : null}
      </section>
    </div>
  )
}

export default Investigation
