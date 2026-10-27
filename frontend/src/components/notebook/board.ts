import type { NotebookContradiction, NotebookEntry, PublicTurn, RumorEdge } from '@/api/types'

export type ClaimMark = 'clean' | 'overlap' | 'conflict'

export interface AlibiChip {
  quote: string
  where: string
  mark: ClaimMark
}

export interface AlibiSlot {
  key: string
  label: string
  minute: number | null
}

export interface AlibiRow {
  suspectId: string
  name: string
  cells: AlibiChip[][]
}

export interface AlibiBoardModel {
  slots: AlibiSlot[]
  rows: AlibiRow[]
}

export interface GraphPerson {
  id: string
  name: string
}

export type GraphChannel = 'confrontation' | 'private' | 'other'

export interface GraphLink {
  id: string
  source: string
  target: string
  text: string
  channel: GraphChannel
}

interface Named {
  id: string
  name: string
}

interface TimedClaim {
  quote: string
  where: string
  from: string
  to: string
}

function norm(value: string): string {
  return value.replace(/\s+/g, ' ').trim().toLowerCase()
}

function parseMinute(raw: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(raw.trim())
  if (!match) return null
  const hour = Number(match[1])
  const minute = Number(match[2])
  if (hour > 23 || minute > 59) return null
  return hour * 60 + minute
}

function formatMinute(minute: number): string {
  const hour = Math.floor(minute / 60) % 24
  const rest = minute % 60
  return `${String(hour).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

function claimRange(from: string, to: string): { lo: number; hi: number } | null {
  const start = parseMinute(from)
  const end = parseMinute(to)
  if (start == null && end == null) return null
  const lo = start ?? end!
  const hi = end ?? start!
  return { lo: Math.min(lo, hi), hi: Math.max(lo, hi) }
}

export function resolveSuspect(ref: string, cast: Named[]): string | null {
  const raw = ref.trim()
  if (!raw) return null
  const key = norm(raw)
  for (const person of cast) {
    if (person.id === raw || norm(person.id) === key || norm(person.name) === key) return person.id
  }
  const hits = cast.filter((person) => {
    const parts = norm(person.name).split(' ').filter((part) => part.length > 2)
    return parts.includes(key)
  })
  return hits.length === 1 ? hits[0]!.id : null
}

function quotesMatch(left: string, right: string): boolean {
  const a = norm(left)
  const b = norm(right)
  return a.length > 0 && a === b
}

export function contradictionMark(con: NotebookContradiction, cast: Named[]): ClaimMark {
  const aId = resolveSuspect(con.a.suspect, cast)
  const bId = resolveSuspect(con.b.suspect_or_evidence, cast)
  if (aId && aId === bId) return 'overlap'
  return 'conflict'
}

function claimMark(suspectId: string, quote: string, contradictions: NotebookContradiction[], cast: Named[]): ClaimMark {
  let mark: ClaimMark = 'clean'
  for (const con of contradictions) {
    const aId = resolveSuspect(con.a.suspect, cast)
    const bId = resolveSuspect(con.b.suspect_or_evidence, cast)
    const onA = aId === suspectId && quotesMatch(con.a.quote, quote)
    const onB = bId === suspectId && quotesMatch(con.b.quote, quote)
    if (!onA && !onB) continue
    const next = contradictionMark(con, cast)
    if (next === 'conflict') return 'conflict'
    mark = next
  }
  return mark
}

export function uniqueClaims<T extends TimedClaim>(claims: T[]): T[] {
  const seen = new Set<string>()
  const unique: T[] = []
  for (const claim of claims) {
    const key = `${norm(claim.quote)}|${norm(claim.where)}|${claim.from.trim()}|${claim.to.trim()}`
    if (seen.has(key)) continue
    seen.add(key)
    unique.push(claim)
  }
  return unique
}

function claimInSlot(claim: TimedClaim, slot: AlibiSlot): boolean {
  const range = claimRange(claim.from, claim.to)
  if (slot.minute == null) return range == null
  if (!range) return false
  return slot.minute >= range.lo && slot.minute <= range.hi
}

function collectSlots(notebook: NotebookEntry | null, timeline: { time: string }[]): AlibiSlot[] {
  const ranges: { lo: number; hi: number }[] = []
  let untimed = false
  for (const suspect of notebook?.per_suspect ?? []) {
    for (const claim of uniqueClaims(suspect.claims)) {
      if (!claim.quote.trim() && !claim.where.trim()) continue
      const range = claimRange(claim.from, claim.to)
      if (!range) {
        untimed = true
        continue
      }
      ranges.push(range)
    }
  }
  const minutes = new Set<number>()
  for (const range of ranges) {
    minutes.add(range.lo)
    minutes.add(range.hi)
  }
  for (const entry of timeline) {
    const minute = parseMinute(entry.time)
    if (minute == null) continue
    if (ranges.some((range) => minute >= range.lo && minute <= range.hi)) minutes.add(minute)
  }
  const slots: AlibiSlot[] = [...minutes]
    .sort((a, b) => a - b)
    .map((minute) => ({ key: String(minute), label: formatMinute(minute), minute }))
  if (untimed || slots.length === 0) slots.push({ key: 'untimed', label: 'No time', minute: null })
  return slots
}

export function buildAlibiBoard(
  cast: Named[],
  notebook: NotebookEntry | null,
  timeline: { time: string }[],
): AlibiBoardModel {
  const slots = collectSlots(notebook, timeline)
  const people = new Map<string, { id: string; name: string; claims: TimedClaim[] }>()
  for (const person of cast) people.set(person.id, { id: person.id, name: person.name, claims: [] })
  for (const suspect of notebook?.per_suspect ?? []) {
    const known = people.get(suspect.id)
    people.set(suspect.id, {
      id: suspect.id,
      name: known?.name ?? suspect.id,
      claims: uniqueClaims(suspect.claims).filter((claim) => claim.quote.trim() || claim.where.trim()),
    })
  }
  const named = [...people.values()].map((person) => ({ id: person.id, name: person.name }))
  const rows: AlibiRow[] = [...people.values()].map((person) => ({
    suspectId: person.id,
    name: person.name,
    cells: slots.map((slot) =>
      person.claims
        .filter((claim) => claimInSlot(claim, slot))
        .map((claim) => ({
          quote: claim.quote,
          where: claim.where,
          mark: claimMark(person.id, claim.quote, notebook?.contradictions ?? [], named),
        })),
    ),
  }))
  return { slots, rows }
}

export function witnessedLinks(turns: PublicTurn[], cast: { id: string }[]): GraphLink[] {
  const ids = new Set(cast.map((person) => person.id))
  const links: GraphLink[] = []
  for (const turn of turns) {
    if (turn.type !== 'confront' || !ids.has(turn.actor)) continue
    const other = turn.other && ids.has(turn.other) ? turn.other : turn.target && ids.has(turn.target) ? turn.target : ''
    if (!other || other === turn.actor) continue
    const text = (turn.spoken ?? '').trim()
    if (!text) continue
    links.push({
      id: `confront-${turn.turn}-${turn.seq}-${links.length}`,
      source: turn.actor,
      target: other,
      text,
      channel: 'confrontation',
    })
  }
  return links
}

export function rumorLinks(edges: RumorEdge[]): GraphLink[] {
  const links: GraphLink[] = []
  edges.forEach((edge, index) => {
    const source = (edge.from ?? '').trim()
    const target = (edge.to ?? '').trim()
    if (!source || !target) return
    const channel: GraphChannel = edge.channel === 'private' || edge.channel === 'confrontation' ? edge.channel : 'other'
    links.push({
      id: `rumor-${edge.turn}-${index}-${source}-${target}`,
      source,
      target,
      text: (edge.text ?? '').trim(),
      channel,
    })
  })
  return links
}

export function graphPeople(cast: Named[], links: GraphLink[]): GraphPerson[] {
  const names = new Map(cast.map((person) => [person.id, person.name]))
  for (const link of links) {
    if (!names.has(link.source)) names.set(link.source, link.source)
    if (!names.has(link.target)) names.set(link.target, link.target)
  }
  return [...names].map(([id, name]) => ({ id, name }))
}

export function linkStroke(channel: GraphChannel): string {
  if (channel === 'confrontation') return '#d23b3b'
  if (channel === 'private') return '#8a8f98'
  return '#c9a24b'
}

export function circlePositions(ids: string[]): Record<string, { x: number; y: number }> {
  const cx = 180
  const cy = 120
  const radius = ids.length <= 1 ? 0 : 88
  const positions: Record<string, { x: number; y: number }> = {}
  ids.forEach((id, index) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / Math.max(ids.length, 1)
    positions[id] = {
      x: cx + radius * Math.cos(angle) - 54,
      y: cy + radius * Math.sin(angle) - 16,
    }
  })
  return positions
}
