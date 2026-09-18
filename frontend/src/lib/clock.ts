/** Clock helpers. The game clock is "HH:MM" (24 h); it starts at 00:15 the night of the murder. */

export interface ParsedClock {
  hours: number
  minutes: number
  /** minutes since midnight */
  total: number
}

/** Parse "HH:MM", "H:MM", "11:35pm", "11.35 pm". Returns null when unparseable. */
export function parseClock(value: string | null | undefined): ParsedClock | null {
  if (!value) return null
  const m = /(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?/i.exec(value)
  if (!m) return null
  let hours = Number(m[1])
  const minutes = Number(m[2])
  const suffix = m[3]?.toLowerCase().replace(/\./g, '')
  if (!Number.isFinite(hours) || !Number.isFinite(minutes) || minutes > 59) return null
  if (suffix === 'pm' && hours < 12) hours += 12
  if (suffix === 'am' && hours === 12) hours = 0
  if (hours > 23) return null
  return { hours, minutes, total: hours * 60 + minutes }
}

/** All clock times found in a free-text string, as minutes since midnight, in order of appearance. */
export function extractTimes(text: string): ParsedClock[] {
  const out: ParsedClock[] = []
  const re = /(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?/gi
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    const p = parseClock(m[0])
    if (p) out.push(p)
  }
  return out
}

export function minutesToHHMM(total: number): string {
  const t = ((total % 1440) + 1440) % 1440
  const h = Math.floor(t / 60)
  const m = t % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** "23:20" → "11:20 PM"; "00:15" → "12:15 AM". */
export function formatClock12(value: string | number): string {
  const p = typeof value === 'number' ? { hours: Math.floor(value / 60) % 24, minutes: value % 60, total: value } : parseClock(value)
  if (!p) return typeof value === 'string' ? value : ''
  const suffix = p.hours >= 12 ? 'PM' : 'AM'
  const h12 = p.hours % 12 === 0 ? 12 : p.hours % 12
  return `${h12}:${String(p.minutes).padStart(2, '0')} ${suffix}`
}

/** Word for the time of night, shown next to the clock. */
export function clockPhase(value: string): string {
  const p = parseClock(value)
  if (!p) return ''
  if (p.hours >= 22) return 'Night'
  if (p.hours >= 5 && p.hours < 7) return 'Dawn'
  if (p.hours >= 7 && p.hours < 12) return 'Morning'
  if (p.hours >= 12 && p.hours < 18) return 'Afternoon'
  if (p.hours >= 18) return 'Evening'
  if (p.hours >= 3) return 'Small hours'
  return 'Night'
}

/** Dawn is close when the clock is at or past 05:00 (and before noon). */
export function isDawn(value: string): boolean {
  const p = parseClock(value)
  return !!p && p.hours >= 5 && p.hours < 12
}
