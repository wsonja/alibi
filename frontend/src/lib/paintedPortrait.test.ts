import { describe, expect, it } from 'vitest'
import {
  paintedAvatarUrl,
  paintedBustUrl,
  paintedNeutralUrl,
  portraitPackForCase,
  preferAvatar,
  resolvePaintedSrc,
} from './paintedPortrait'

describe('paintedPortrait', () => {
  it('maps vane_hall case ids to the pack folder', () => {
    expect(portraitPackForCase('vane_hall_1923')).toBe('vane_hall')
    expect(portraitPackForCase('vane_hall')).toBe('vane_hall')
    expect(portraitPackForCase('rms_caledonia')).toBeNull()
  })

  it('prefers avatars for small chips and busts for the room', () => {
    expect(preferAvatar(56)).toBe(true)
    expect(preferAvatar(96)).toBe(false)
    expect(paintedAvatarUrl('vane_hall', 'margaret')).toBe('/portraits/vane_hall/margaret_avatar.webp')
    expect(paintedBustUrl('vane_hall', 'pell', 'angry')).toBe('/portraits/vane_hall/pell_angry.webp')
    expect(paintedNeutralUrl('vane_hall', 'ada')).toBe('/portraits/vane_hall/ada_neutral.webp')
  })

  it('falls back emotion → neutral for busts; uses avatar for list size', () => {
    const bust = resolvePaintedSrc({ caseId: 'vane_hall_1923', suspectId: 'crane', emotion: 'nervous', size: 160 })
    expect(bust).toEqual({
      pack: 'vane_hall',
      src: '/portraits/vane_hall/crane_nervous.webp',
      fallbackSrc: '/portraits/vane_hall/crane_neutral.webp',
    })

    const chip = resolvePaintedSrc({ suspectId: 'margaret', emotion: 'sad', size: 56 })
    expect(chip?.src).toBe('/portraits/vane_hall/margaret_avatar.webp')

    expect(resolvePaintedSrc({ suspectId: 'unknown', size: 96 })).toBeNull()
  })
})
