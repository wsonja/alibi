// placeholder — replaced by the Debrief+Judge+Archive lane
// Route /archive. Lists past games from GET /games so the contract is exercised now.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '@/api/client'
import type { GameSummary } from '@/api/types'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { Marquee } from '@/components/common/Marquee'
import { SectionTitle } from '@/components/common/SectionTitle'

export function Archive() {
  const [games, setGames] = useState<GameSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setError(null)
    api
      .listGames()
      .then((g) => {
        if (!cancelled) setGames(g)
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e))
      })
    return () => {
      cancelled = true
    }
  }, [tick])

  return (
    <div className="screen">
      <header className="flex justify-center">
        <Marquee />
      </header>
      <section className="parchment mt-6">
        <SectionTitle subtitle="New people. New lies. Every time.">Campaign / Case Archive</SectionTitle>
        {error ? <ErrorNotice message={error} onRetry={() => setTick((t) => t + 1)} /> : null}
        {games ? (
          games.length ? (
            <ul className="list-none p-0 m-0 flex flex-col gap-2">
              {games.map((g) => (
                <li key={g.game_id} className="flex flex-wrap items-baseline gap-3">
                  <Link to={g.status === 'closed' ? `/game/${g.game_id}/debrief` : `/game/${g.game_id}`} className="label-caps">
                    {g.case_title}
                  </Link>
                  <span className="ink-soft" style={{ fontSize: 14 }}>
                    {g.difficulty} · {g.status} · turn {g.turn}
                    {g.rank ? ` · ${g.rank}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="ink-soft">No games yet. This screen is a placeholder; the Archive lane replaces it.</p>
          )
        ) : !error ? (
          <p className="ink-soft">Loading…</p>
        ) : null}
        <p className="mt-4">
          <Link to="/" className="placard">
            ◀ New case
          </Link>
        </p>
      </section>
    </div>
  )
}

export default Archive
