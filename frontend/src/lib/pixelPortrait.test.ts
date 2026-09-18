import { describe, expect, it } from 'vitest'
import { GRID_H, GRID_W, PORTRAIT_EMOTIONS, buildPortrait, describeTraits, gridToSvg, parseTraits, portraitAlt, portraitFor, toPortraitEmotion } from './pixelPortrait'

/** The four Vane Hall prompts (backend/app/cases/vane_hall.json). */
const VANE_HALL = {
  margaret: '1920s English aristocratic woman, mid-forties, dark hair pinned up, pearl earrings, high-necked evening dress, composed and cold, painterly portrait, dim lamplight',
  crane: '1920s English country doctor, fifty, grey at the temples, tired kind eyes, tweed waistcoat under a dinner jacket, painterly portrait, lamplight',
  pell: '1920s English businessman, early forties, handsome, brilliantined hair, easy confident smile, dinner jacket, cigar, painterly portrait, lamplight',
  ada: '1920s English housemaid, early twenties, cap and apron, sharp watchful eyes, tired, painterly portrait, lamplight',
} as const

describe('parseTraits', () => {
  it('reads Lady Margaret: dark hair in a bun, pearls, evening dress, cold', () => {
    const t = parseTraits(VANE_HALL.margaret)
    expect(t.hairColor).toBe('black')
    expect(t.hairStyle).toBe('bun')
    expect(t.pearls).toBe(true)
    expect(t.earrings).toBe(true)
    expect(t.clothing).toBe('evening')
    expect(t.cold).toBe(true)
    expect(t.age).toBe('middle')
    expect(t.presentation).toBe('feminine')
    expect(t.cigar).toBe(false)
    expect(t.headwear).toBe('none')
  })

  it('reads Dr. Crane: grey temples, tired, tweed waistcoat, spectacles (doctor)', () => {
    const t = parseTraits(VANE_HALL.crane)
    expect(t.greyTemples).toBe(true)
    expect(t.hairColor).toBe('brown') // temples only — base colour stays
    expect(t.tired).toBe(true)
    expect(t.clothing).toBe('tweed')
    expect(t.spectacles).toBe(true)
    expect(t.presentation).toBe('masculine')
    expect(t.hairStyle).toBe('short')
  })

  it('reads Thomas Pell: slicked hair, smile, dinner jacket, cigar', () => {
    const t = parseTraits(VANE_HALL.pell)
    expect(t.hairStyle).toBe('slicked')
    expect(t.smile).toBe(true)
    expect(t.clothing).toBe('dinner')
    expect(t.cigar).toBe(true)
    expect(t.age).toBe('middle')
    expect(t.spectacles).toBe(false)
  })

  it('reads Ada Finch: white cap, apron, sharp eyes, tired, young', () => {
    const t = parseTraits(VANE_HALL.ada)
    expect(t.headwear).toBe('cap')
    expect(t.clothing).toBe('apron')
    expect(t.sharpEyes).toBe(true)
    expect(t.tired).toBe(true)
    expect(t.age).toBe('young')
    expect(t.presentation).toBe('feminine')
  })

  it('handles other keyword families', () => {
    expect(parseTraits('a bald old man with a white beard and a monocle, military uniform').hairStyle).toBe('bald')
    expect(parseTraits('a bald old man with a white beard and a monocle, military uniform').beard).toBe(true)
    expect(parseTraits('a bald old man with a white beard and a monocle, military uniform').monocle).toBe(true)
    expect(parseTraits('a bald old man with a white beard and a monocle, military uniform').clothing).toBe('military')
    expect(parseTraits('young woman, red curls, cloche hat, blue eyes, pale').hairColor).toBe('red')
    expect(parseTraits('young woman, red curls, cloche hat, blue eyes, pale').hairStyle).toBe('curls')
    expect(parseTraits('young woman, red curls, cloche hat, blue eyes, pale').headwear).toBe('cloche')
    expect(parseTraits('young woman, red curls, cloche hat, blue eyes, pale').eyeColor).toBe('blue')
    expect(parseTraits('young woman, red curls, cloche hat, blue eyes, pale').skin).toBe('fair')
    expect(parseTraits('man in a fedora and trench coat, moustache, olive skin, dark hair').headwear).toBe('fedora')
    expect(parseTraits('man in a fedora and trench coat, moustache, olive skin, dark hair').moustache).toBe(true)
    expect(parseTraits('man in a fedora and trench coat, moustache, olive skin, dark hair').skin).toBe('olive')
    expect(parseTraits('dark-skinned woman in a blonde bob, hoodie').skin).toBe('dark')
    expect(parseTraits('dark-skinned woman in a blonde bob, hoodie').hairColor).toBe('blonde')
    expect(parseTraits('dark-skinned woman in a blonde bob, hoodie').clothing).toBe('hoodie')
    expect(parseTraits('').presentation).toBe('unknown')
    expect(parseTraits(null).hairColorExplicit).toBe(false)
  })

  it('describes traits in one line', () => {
    expect(describeTraits(parseTraits(VANE_HALL.ada))).toContain('a white cap')
    expect(describeTraits(parseTraits(VANE_HALL.pell))).toContain('a cigar')
  })
})

describe('buildPortrait', () => {
  const suspects = Object.entries(VANE_HALL) as Array<[keyof typeof VANE_HALL, string]>

  it('renders a full 24×28 grid for each Vane Hall prompt in every emotion', () => {
    for (const [id, prompt] of suspects) {
      for (const emotion of PORTRAIT_EMOTIONS) {
        const grid = portraitFor(prompt, id, emotion)
        expect(grid.w).toBe(GRID_W)
        expect(grid.h).toBe(GRID_H)
        expect(grid.cells).toHaveLength(GRID_W * GRID_H)
        const painted = grid.cells.filter(Boolean).length
        expect(painted).toBeGreaterThan(300)
        // every painted cell is a hex colour
        for (const c of grid.cells) if (c) expect(c).toMatch(/^#[0-9a-f]{6}$/)
      }
    }
  })

  it('is deterministic for the same seed and differs between suspects', () => {
    const a1 = portraitFor(VANE_HALL.pell, 'pell')
    const a2 = portraitFor(VANE_HALL.pell, 'pell')
    expect(a1.cells).toEqual(a2.cells)
    const grids = suspects.map(([id, prompt]) => portraitFor(prompt, id).cells.join(','))
    expect(new Set(grids).size).toBe(4)
  })

  it('changes with emotion and with blinking', () => {
    const neutral = portraitFor(VANE_HALL.ada, 'ada', 'neutral')
    for (const emotion of PORTRAIT_EMOTIONS.filter((e) => e !== 'neutral')) {
      expect(portraitFor(VANE_HALL.ada, 'ada', emotion).cells).not.toEqual(neutral.cells)
    }
    expect(portraitFor(VANE_HALL.ada, 'ada', 'neutral', true).cells).not.toEqual(neutral.cells)
  })

  it('draws the distinctive props: cap on Ada, cigar ember on Pell, pearls on Margaret, spectacle rims on Crane', () => {
    const at = (grid: ReturnType<typeof portraitFor>, x: number, y: number) => grid.cells[y * GRID_W + x]
    const ada = portraitFor(VANE_HALL.ada, 'ada')
    expect(at(ada, 12, 4)).toBe('#f4efe4') // white cap
    const pell = portraitFor(VANE_HALL.pell, 'pell')
    expect(at(pell, 17, 17)).toBe('#e8602a') // ember
    const margaret = portraitFor(VANE_HALL.margaret, 'margaret')
    expect(at(margaret, 10, 23)).toBe('#f3efe6') // pearl
    expect(at(margaret, 11, 23)).toBe('#cfc8ba') // pearl (shaded)
    expect(at(margaret, 11, 2)).toBeTruthy() // bun sits above the head
    const crane = portraitFor(VANE_HALL.crane, 'crane')
    const rim = at(crane, 6, 11)
    expect(rim === '#c9a24b' || rim === '#2a2118').toBe(true) // spectacle rim (gold wire or dark horn)
    expect(at(crane, 5, 9)).toBe('#9a9a94') // grey temple
  })

  it('exports SVG with a title', () => {
    const svg = gridToSvg(portraitFor(VANE_HALL.crane, 'crane'), { title: portraitAlt('Dr. Elias Crane', 'neutral'), size: 96 })
    expect(svg.startsWith('<svg')).toBe(true)
    expect(svg).toContain('<title>Portrait of Dr. Elias Crane, looking neutral</title>')
    expect(svg).toContain('shape-rendering="crispEdges"')
    expect((svg.match(/<rect/g) ?? []).length).toBeGreaterThan(100)
  })

  it('can skip the background disc and maps unknown emotions to neutral', () => {
    const noDisc = buildPortrait({ traits: parseTraits(VANE_HALL.ada), seed: 'ada', disc: false })
    expect(noDisc.cells[0]).toBeNull()
    expect(toPortraitEmotion('bewildered')).toBe('neutral')
    expect(toPortraitEmotion('smug')).toBe('smug')
  })
})
