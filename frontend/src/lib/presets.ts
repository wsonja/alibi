/** The five setting tiles on the New Case screen (DESIGN §5.1) and how installed cases map onto them. */
import type { CasePreset, CaseSummary } from '@/api/types'

export interface PresetTile {
  id: CasePreset
  label: string
  blurb: string
  /** Setting sentence sent to the Author when generating a case for this tile. */
  generationSetting: string
  camera?: boolean
}

export const PRESET_TILES: readonly PresetTile[] = [
  {
    id: 'manor',
    label: 'Manor 1923',
    blurb: 'A country house, a storm, a locked study.',
    generationSetting: 'An English country house on a stormy night in 1923. A dinner party; the telephone line is down.',
  },
  {
    id: 'liner',
    label: 'Ocean liner',
    blurb: 'First class, mid-Atlantic, no way off.',
    generationSetting: 'A first-class deck of a transatlantic ocean liner in 1931, three days from any port.',
  },
  {
    id: 'startup',
    label: 'Startup office',
    blurb: 'Glass walls, a launch party, one founder fewer.',
    generationSetting: 'A late-night launch party at a venture-backed startup office in a modern city, the night before the funding round closes.',
  },
  {
    id: 'dorm',
    label: 'Cornell dorm',
    blurb: 'Finals week on the hill. Someone did not make it to the exam.',
    generationSetting: 'A residence hall at Cornell University during finals week in a snowy December; the RA found the body at dawn.',
  },
  {
    id: 'room',
    label: 'Your room',
    blurb: 'Describe the scene. The cast writes itself.',
    generationSetting: '',
    camera: true,
  },
]

export function presetLabel(preset: CasePreset): string {
  return PRESET_TILES.find((p) => p.id === preset)?.label ?? 'Other'
}

/** Installed cases for a tile (hand-written first, then generated, newest last). */
export function casesForPreset(cases: CaseSummary[], preset: CasePreset): CaseSummary[] {
  return cases.filter((c) => c.preset === preset).sort((a, b) => Number(a.generated) - Number(b.generated))
}

/** Guess a preset from a setting string — mirrors the backend's keyword rule, used for cases without `preset`. */
export function presetFromSetting(setting: string): CasePreset {
  const s = setting.toLowerCase()
  if (/\b(manor|hall|country house|estate|mansion|19[0-3]\d)\b/.test(s)) return 'manor'
  if (/\b(liner|ship|steamer|cruise|deck|voyage|atlantic)\b/.test(s)) return 'liner'
  if (/\b(startup|start-up|office|founder|tech|launch)\b/.test(s)) return 'startup'
  if (/\b(dorm|campus|cornell|college|university|residence hall)\b/.test(s)) return 'dorm'
  if (/\b(my room|your room|bedroom|apartment|flat)\b/.test(s)) return 'room'
  return 'other'
}
