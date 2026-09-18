// placeholder — replaced by the Debrief+Judge+Archive lane
// Route /game/:id/debrief. Loads the Debrief so the contract is exercised now.
import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { ButtonLink } from '@/components/common/Button'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { Marquee } from '@/components/common/Marquee'
import { useGame } from '@/store/game'

export function Debrief() {
  const { id = '' } = useParams()
  const debrief = useGame((s) => s.debrief)
  const error = useGame((s) => s.error)
  const loadDebrief = useGame((s) => s.loadDebrief)

  useEffect(() => {
    if (id && (!debrief || debrief.game_id !== id)) void loadDebrief(id)
  }, [id, debrief, loadDebrief])

  return (
    <div className="screen">
      <header className="flex justify-center">
        <Marquee />
      </header>
      <section className="parchment mt-6">
        <h1 className="display ink" style={{ fontSize: 18, marginTop: 0 }}>
          Case closed
        </h1>
        {debrief ? (
          <p>
            {debrief.correct ? 'Correct! You found the truth.' : 'Wrong. The truth was elsewhere.'} Rank: <strong>{debrief.rank}</strong> · Score {debrief.score.total}. The murderer was <strong>{debrief.truth.murderer_name}</strong>.
          </p>
        ) : error ? (
          <ErrorNotice message={error} onRetry={() => void loadDebrief(id)} />
        ) : (
          <p className="ink-soft">Loading the debrief… (this screen is a placeholder; the Debrief lane replaces it)</p>
        )}
        <div className="flex gap-3 flex-wrap">
          <ButtonLink to={`/game/${id}`} variant="black">
            ◀ Back to the room
          </ButtonLink>
          <ButtonLink to="/">New case</ButtonLink>
        </div>
      </section>
    </div>
  )
}

export default Debrief
