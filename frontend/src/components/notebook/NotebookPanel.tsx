import { useEffect, useMemo, useState } from 'react'
import type { NotebookEntry, PublicEvidence, PublicSuspect, PublicTurn, TimelineEntry } from '@/api/types'
import { EvidenceArt } from '@/components/common/EvidenceArt'
import { SectionTitle } from '@/components/common/SectionTitle'
import { Sticky } from '@/components/common/Sticky'
import { cn } from '@/lib/cn'
import { describeTurn } from '@/store/game'
import { useSensors } from '@/store/sensors'
import { AlibiBoard } from './AlibiBoard'
import { graphPeople, uniqueClaims, witnessedLinks } from './board'
import { CastGraph } from './CastGraph'

const TABS = [
  { id: 'notes', label: 'Notes' },
  { id: 'alibi', label: 'Alibi Board' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'graph', label: 'Graph' },
] as const

type NotebookTab = (typeof TABS)[number]['id']

function evidenceRank(evidence: PublicEvidence): number {
  if (evidence.state === 'examined') return 0
  if (evidence.state === 'known') return 1
  if (evidence.state === 'destroyed') return 2
  return 3
}

function claimLine(where: string, from: string, to: string, quote: string): string {
  const place = where.trim()
  const start = from.trim()
  const end = to.trim()
  const when = start && end && start !== end ? `${start} to ${end}` : start || end
  const head = [place, when].filter(Boolean).join(', ')
  return head ? `${head}. ${quote}` : quote
}

function NotesTab({ cast, turns, notebook }: { cast: PublicSuspect[]; turns: PublicTurn[]; notebook: NotebookEntry | null }) {
  const names = new Map(cast.map((person) => [person.id, person.name]))
  if (!notebook) {
    const lines = turns
      .slice(-6)
      .map((turn) => describeTurn(turn, cast))
      .filter(Boolean)
      .reverse()
    return (
      <>
        <h3 className="label-caps" style={{ margin: 0 }}>
          Working notes
        </h3>
        <ul className="flex flex-col gap-1 list-none p-0 m-0" style={{ fontSize: 13 }}>
          {lines.length === 0 ? <li className="ink-soft">Nothing yet. Ask someone something.</li> : null}
          {lines.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
        <p className="ink-soft" style={{ fontSize: 13, marginBottom: 0 }}>
          Watson has not updated the notebook yet.
        </p>
      </>
    )
  }

  const pinned = notebook.suggested_next[0]

  return (
    <>
      {notebook.per_suspect.map((suspect) => {
        const empty = suspect.notes.length === 0 && suspect.claims.length === 0
        return (
          <section key={suspect.id}>
            <h3 className="label-caps" style={{ margin: '0 0 4px' }}>
              {names.get(suspect.id) ?? suspect.id}
            </h3>
            <ul className="flex flex-col gap-1 list-none p-0 m-0" style={{ fontSize: 13 }}>
              {empty ? <li className="ink-soft">Nothing filed.</li> : null}
              {suspect.notes.map((note, index) => (
                <li key={`n-${index}`}>{note}</li>
              ))}
              {uniqueClaims(suspect.claims).map((claim, index) => (
                <li key={`c-${index}`}>{claimLine(claim.where, claim.from, claim.to, claim.quote)}</li>
              ))}
            </ul>
          </section>
        )
      })}
      <h3 className="label-caps" style={{ margin: 0 }}>
        Working notes
      </h3>
      <ul className="flex flex-col gap-1 list-none p-0 m-0" style={{ fontSize: 13 }}>
        {notebook.suggested_next.length === 0 ? <li className="ink-soft">No next step yet.</li> : null}
        {notebook.suggested_next.map((line, index) => (
          <li key={index}>{line}</li>
        ))}
      </ul>
      {pinned ? (
        <Sticky style={{ maxWidth: '100%', fontSize: 18 }}>{pinned}</Sticky>
      ) : null}
    </>
  )
}

function EvidenceTab({ evidence, caseId }: { evidence: PublicEvidence[]; caseId: string }) {
  const visible = [...evidence].filter((item) => item.state === 'examined' || item.state === 'known' || item.state === 'destroyed').sort((a, b) => evidenceRank(a) - evidenceRank(b))
  if (visible.length === 0) {
    return (
      <p className="ink-soft" style={{ fontSize: 13, margin: 0 }}>
        Nothing in the notebook yet. Search a room.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-2 list-none p-0 m-0">
      {visible.map((item) => (
        <li key={item.id} style={{ opacity: item.state === 'examined' ? 1 : 0.55 }}>
          <div className="flex items-start gap-2">
            <EvidenceArt
              caseId={caseId}
              evidenceId={item.id}
              name={item.name}
              description={item.description}
              size={36}
              fit="contain"
              iconColor="var(--wood-600)"
            />
            <div className="min-w-0">
              <div style={{ fontWeight: 700, fontSize: 13 }}>{item.name}</div>
              <div style={{ fontSize: 12 }}>{item.state === 'examined' && item.examined_detail ? item.examined_detail : item.description}</div>
              {item.state === 'known' ? (
                <div className="ink-soft" style={{ fontSize: 11 }}>
                  Not examined
                </div>
              ) : null}
              {item.state === 'destroyed' ? (
                <div className="ink-soft" style={{ fontSize: 11 }}>
                  Destroyed
                </div>
              ) : null}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}

export function NotebookPanel({
  cast,
  evidence,
  turns,
  notebook,
  timeline,
  caseId,
}: {
  cast: PublicSuspect[]
  evidence: PublicEvidence[]
  turns: PublicTurn[]
  notebook: NotebookEntry | null
  timeline: TimelineEntry[]
  caseId: string
}) {
  const [tab, setTab] = useState<NotebookTab>('notes')
  const links = useMemo(() => witnessedLinks(turns, cast), [turns, cast])
  const graphCast = useMemo(() => graphPeople(cast, links), [cast, links])

  useEffect(() => {
    useSensors.getState().setEvidenceTabOpen(tab === 'evidence')
    return () => useSensors.getState().setEvidenceTabOpen(false)
  }, [tab])

  return (
    <section className="parchment parchment--tight flex flex-col gap-3 min-w-0 max-w-full" aria-label="Detective's notebook">
      <SectionTitle as="h2" align="left">
        Notebook
      </SectionTitle>
      <div className="tab-bar tab-bar--parchment tab-bar--notebook" role="tablist" aria-label="Notebook pages">
        {TABS.map((item) => (
          <button key={item.id} type="button" role="tab" id={`notebook-tab-${item.id}`} aria-selected={tab === item.id} aria-controls={`notebook-panel-${item.id}`} className={cn('tab', tab === item.id && 'active')} onClick={() => setTab(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`notebook-panel-${tab}`} aria-labelledby={`notebook-tab-${tab}`} className="flex flex-col gap-3 min-w-0 max-w-full">
        {tab === 'notes' ? <NotesTab cast={cast} turns={turns} notebook={notebook} /> : null}
        {tab === 'alibi' ? <AlibiBoard cast={cast} notebook={notebook} timeline={timeline} /> : null}
        {tab === 'evidence' ? <EvidenceTab evidence={evidence} caseId={caseId} /> : null}
        {tab === 'graph' ? (
          <CastGraph
            people={graphCast}
            links={links}
            label="Relationship graph"
            tone="paper"
            emptyNote="No one has accused anyone in what you have heard. Confront two suspects and the lines they speak show up here."
          />
        ) : null}
      </div>
    </section>
  )
}
