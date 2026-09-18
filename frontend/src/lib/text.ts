/** Small text helpers used by the Briefing and cast components. */
import type { PublicEvidence, PublicLocation, TimelineEntry } from '@/api/types'
import { extractTimes, formatClock12, minutesToHHMM, parseClock } from './clock'

/** Split a paragraph into sentences (keeps the terminal punctuation). */
export function sentences(text: string): string[] {
  return (text.match(/[^.!?]+[.!?]+(?:["'”’])?|[^.!?]+$/g) ?? []).map((s) => s.trim()).filter(Boolean)
}

/**
 * The stated alibi inside a `public_description`: the sentence that starts with "Says"/"Claims"/"Insists"…
 * Falls back to the last sentence, then to the whole description.
 */
export function extractAlibi(publicDescription: string): string {
  const parts = sentences(publicDescription)
  const hit = parts.find((s) => /^(says|claims|insists|maintains|states|tells|swears)\b/i.test(s))
  if (hit) return hit
  return parts.length > 1 ? parts[parts.length - 1]! : publicDescription
}

/** First-name-ish label for compact UI: "Lady Margaret Vane" → "Margaret", "Dr. Elias Crane" → "Crane". */
export function shortName(fullName: string): string {
  const words = fullName.replace(/\./g, '').split(/\s+/).filter(Boolean)
  const honorifics = new Set(['lady', 'lord', 'sir', 'dr', 'mr', 'mrs', 'ms', 'miss', 'prof', 'professor', 'captain', 'colonel', 'major', 'rev'])
  const rest = words.filter((w) => !honorifics.has(w.toLowerCase()))
  if (rest.length === 0) return fullName
  // Doctors and misters go by surname; everyone else by first name.
  const first = words[0]?.toLowerCase() ?? ''
  if ((first === 'dr' || first === 'mr' || first === 'mrs' || first === 'ms' || first === 'miss') && rest.length > 1) return rest[rest.length - 1]!
  return rest[0]!
}

export interface DeathWindow {
  /** "HH:MM" 24 h */
  from: string
  to: string
  /** "11:20 – 11:35 PM" */
  label: string
}

/**
 * Time-of-death window, derived from the public cause-of-death text and the public timeline (DESIGN §5.2):
 * end = the first time mentioned in the cause text (the collapse), else the timeline entry where the body is found;
 * start = the latest timeline time strictly before that (else 30 minutes earlier).
 */
export function deriveDeathWindow(timeline: TimelineEntry[], causeText: string): DeathWindow | null {
  const timesInCause = extractTimes(causeText)
  const found = timeline.find((t) => /\b(found|dead|body|collapse|collapsed|discover)/i.test(t.event))
  const endMinutes = timesInCause[0]?.total ?? (found ? parseClock(found.time)?.total : undefined) ?? parseClock(timeline[timeline.length - 1]?.time)?.total
  if (endMinutes == null) return null
  const before = timeline
    .map((t) => parseClock(t.time)?.total)
    .filter((t): t is number => t != null && t < endMinutes)
  const startMinutes = before.length ? Math.max(...before) : endMinutes - 30
  const from = minutesToHHMM(startMinutes)
  const to = minutesToHHMM(endMinutes)
  const fromLabel = formatClock12(from)
  const toLabel = formatClock12(to)
  const sameSuffix = fromLabel.slice(-2) === toLabel.slice(-2)
  const label = sameSuffix ? `${fromLabel.slice(0, -3)} – ${toLabel}` : `${fromLabel} – ${toLabel}`
  return { from, to, label }
}

/** The crime scene: the location of the first initially-known evidence, else a location named in the briefing, else the first. */
export function deriveCrimeScene(locations: PublicLocation[], evidence: PublicEvidence[], briefing: string): PublicLocation | null {
  if (!locations.length) return null
  const known = evidence.find((e) => e.state === 'known' || e.state === 'examined')
  if (known) {
    const loc = locations.find((l) => l.id === known.location)
    if (loc) return loc
  }
  const lower = briefing.toLowerCase()
  const named = locations.find((l) => lower.includes(l.name.toLowerCase().replace(/^the /, '')))
  return named ?? locations[0]!
}

/** Clamp + pluralise: n === 1 ? "1 person" : "n people" (words are spelled out up to ten). */
const NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
export function numberWord(n: number): string {
  return NUMBER_WORDS[n] ?? String(n)
}

export function truncate(text: string, max = 120): string {
  if (text.length <= max) return text
  return `${text.slice(0, max - 1).trimEnd()}…`
}
