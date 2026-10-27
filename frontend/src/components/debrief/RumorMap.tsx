import { useMemo } from 'react'
import type { PublicSuspect, RumorEdge } from '@/api/types'
import { SectionTitle } from '@/components/common/SectionTitle'
import { CastGraph } from '@/components/notebook/CastGraph'
import { graphPeople, rumorLinks } from '@/components/notebook/board'

export function RumorMap({ cast, edges }: { cast: PublicSuspect[]; edges: RumorEdge[] }) {
  const links = useMemo(() => rumorLinks(edges ?? []), [edges])
  const people = useMemo(() => graphPeople(cast, links), [cast, links])

  return (
    <section className="lacquer mt-4" aria-label="Rumor map">
      <SectionTitle as="h2" dark align="left" subtitle="How the story spread">
        Rumor Map
      </SectionTitle>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        Grey edges are private messages. Red edges are accusations from a confrontation. Select a line to read it.
      </p>
      <CastGraph
        people={people}
        links={links}
        label="Rumor map"
        tone="lacquer"
        height={340}
        emptyNote="No rumors passed while you were investigating."
      />
    </section>
  )
}
