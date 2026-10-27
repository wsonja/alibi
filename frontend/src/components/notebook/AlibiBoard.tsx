import type { NotebookEntry, TimelineEntry } from '@/api/types'
import { cn } from '@/lib/cn'
import { buildAlibiBoard, contradictionMark, type AlibiChip } from './board'

function Chip({ chip }: { chip: AlibiChip }) {
  return (
    <span className={cn('alibi-chip', chip.mark !== 'clean' && `alibi-chip--${chip.mark}`)} data-mark={chip.mark} title={chip.quote}>
      {chip.mark === 'overlap' ? <span className="sr-only">Overlapping alibi. </span> : null}
      {chip.mark === 'conflict' ? <span className="sr-only">Conflicting alibi. </span> : null}
      {chip.where || 'Unplaced'}
    </span>
  )
}

export function AlibiBoard({
  cast,
  notebook,
  timeline,
}: {
  cast: { id: string; name: string }[]
  notebook: NotebookEntry | null
  timeline: TimelineEntry[]
}) {
  const model = buildAlibiBoard(cast, notebook, timeline)
  const filed = (notebook?.per_suspect ?? []).some((suspect) => suspect.claims.some((claim) => claim.quote || claim.where))

  return (
    <div>
      {!notebook ? (
        <p className="ink-soft" style={{ fontSize: 13, marginTop: 0 }}>
          Watson has not filed claims yet.
        </p>
      ) : null}
      {notebook && !filed ? (
        <p className="ink-soft" style={{ fontSize: 13, marginTop: 0 }}>
          No claims yet. Ask where they were.
        </p>
      ) : null}
      <div className="scroll-x alibi-scroll">
        <table className="alibi-board">
          <caption className="sr-only">Alibis by suspect and time</caption>
          <thead>
            <tr>
              <th scope="col">Suspect</th>
              {model.slots.map((slot) => (
                <th key={slot.key} scope="col">
                  {slot.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.rows.map((row) => (
              <tr key={row.suspectId}>
                <th scope="row">{row.name}</th>
                {row.cells.map((chips, index) => (
                  <td key={model.slots[index]!.key}>
                    {chips.length === 0 ? <span className="sr-only">No claim</span> : null}
                    {chips.map((chip, chipIndex) => (
                      <Chip key={`${row.suspectId}-${index}-${chipIndex}`} chip={chip} />
                    ))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ink-soft" style={{ fontSize: 12, marginBottom: 0 }}>
        <span className="alibi-chip alibi-chip--overlap">Overlap</span> the same person, two places.{' '}
        <span className="alibi-chip alibi-chip--conflict">Conflict</span> another account or a clue disagrees.
      </p>
      {notebook && notebook.contradictions.length > 0 ? (
        <ul className="alibi-notes">
          {notebook.contradictions.map((con, index) => {
            const mark = contradictionMark(con, cast)
            const text = con.note.trim() || `${con.a.quote} / ${con.b.quote}`
            return (
              <li key={index} className={cn('alibi-note', `alibi-note--${mark}`)}>
                {text}
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
