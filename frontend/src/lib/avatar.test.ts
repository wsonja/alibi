import { describe, expect, it } from 'vitest'
import { AVATAR_H, AVATAR_PALETTE, AVATAR_W, autoLevels, avatarFromPixels, cropRect, fromAvatarRecord, nearestColor, quantize, sampleColors, toAvatarRecord, vignette, type RgbaSource } from './avatar'

/** Build an RGBA source from a painter callback. */
function source(width: number, height: number, paint: (x: number, y: number) => [number, number, number]): RgbaSource {
  const data = new Uint8ClampedArray(width * height * 4)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const [r, g, b] = paint(x, y)
      const i = (y * width + x) * 4
      data[i] = r
      data[i + 1] = g
      data[i + 2] = b
      data[i + 3] = 255
    }
  }
  return { width, height, data }
}

describe('cropRect', () => {
  it('is a centred 6:7 box covering 82% of the height on a landscape frame', () => {
    const c = cropRect(640, 480)
    expect(c.sh).toBeCloseTo(480 * 0.82)
    expect(c.sw / c.sh).toBeCloseTo(AVATAR_W / AVATAR_H)
    expect(c.sx).toBeCloseTo((640 - c.sw) / 2)
    expect(c.sy).toBeCloseTo((480 - c.sh) / 2)
  })

  it('never exceeds the frame width on a tall, narrow frame', () => {
    const c = cropRect(100, 1000)
    expect(c.sw).toBe(100)
    expect(c.sx).toBe(0)
    expect(c.sh).toBeCloseTo((100 * AVATAR_H) / AVATAR_W)
  })
})

describe('sampleColors', () => {
  it('averages each source block into one cell', () => {
    // 4×4 source split into four solid quadrants → a 2×2 grid reproduces them exactly
    const src = source(4, 4, (x, y) => (y < 2 ? (x < 2 ? [255, 0, 0] : [0, 255, 0]) : x < 2 ? [0, 0, 255] : [255, 255, 255]))
    const rgb = sampleColors(src, 2, 2)
    expect(Array.from(rgb)).toEqual([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
  })

  it('blends when a cell covers mixed pixels', () => {
    const src = source(2, 1, (x) => (x === 0 ? [0, 0, 0] : [200, 100, 50]))
    const rgb = sampleColors(src, 1, 1)
    expect(Array.from(rgb)).toEqual([100, 50, 25])
  })

  it('upsamples a source smaller than the grid without reading outside it', () => {
    const src = source(2, 2, () => [10, 20, 30])
    const rgb = sampleColors(src, 6, 7)
    expect(rgb.length).toBe(6 * 7 * 3)
    for (let i = 0; i < 6 * 7; i++) expect(Array.from(rgb.slice(i * 3, i * 3 + 3))).toEqual([10, 20, 30])
  })
})

describe('autoLevels', () => {
  it('stretches a flat, dim ramp to the full range', () => {
    const n = 100
    const rgb = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      const v = 60 + i * 0.5 // 60 … 109.5: washed-out webcam grey
      rgb[i * 3] = v
      rgb[i * 3 + 1] = v
      rgb[i * 3 + 2] = v
    }
    const out = autoLevels(rgb)
    expect(out[0]).toBeLessThan(10)
    expect(out[(n - 1) * 3]).toBeGreaterThan(245)
  })

  it('leaves a near-uniform frame alone', () => {
    const rgb = Float32Array.from([120, 120, 120, 121, 121, 121, 122, 122, 122])
    expect(Array.from(autoLevels(rgb))).toEqual(Array.from(rgb))
  })
})

describe('vignette', () => {
  it('keeps the centre and darkens the corners', () => {
    const w = 5
    const h = 5
    const rgb = new Float32Array(w * h * 3).fill(200)
    const out = vignette(rgb, w, h, 0.5)
    const centre = (2 * w + 2) * 3
    expect(out[centre]).toBeCloseTo(200)
    expect(out[0]).toBeCloseTo(100)
  })
})

describe('nearestColor / quantize', () => {
  it('maps a palette colour onto itself and off-palette colours onto a palette entry', () => {
    expect(nearestColor(0xf4, 0xdc, 0xc4)).toBe('#f4dcc4')
    const c = nearestColor(3, 2, 1)
    expect(AVATAR_PALETTE).toContain(c)
    expect(c).toBe('#100b08') // the darkest swatch
  })

  it('produces a grid whose every cell is a palette colour', () => {
    const rgb = Float32Array.from([255, 255, 255, 0, 0, 0, 128, 64, 32, 10, 200, 10])
    const grid = quantize(rgb, 2, 2)
    expect(grid.w).toBe(2)
    expect(grid.h).toBe(2)
    expect(grid.cells).toHaveLength(4)
    for (const c of grid.cells) expect(AVATAR_PALETTE).toContain(c)
  })
})

describe('avatarFromPixels', () => {
  it('returns a 36×42 grid, deterministic for the same pixels', () => {
    const src = source(144, 168, (x, y) => [(x * 255) / 144, (y * 255) / 168, 128])
    const a = avatarFromPixels(src)
    const b = avatarFromPixels(src)
    expect(a.w).toBe(AVATAR_W)
    expect(a.h).toBe(AVATAR_H)
    expect(a.cells).toHaveLength(AVATAR_W * AVATAR_H)
    expect(a.cells).toEqual(b.cells)
    expect(a.cells.every((c) => c !== null)).toBe(true)
  })
})

describe('avatar records', () => {
  it('round-trips through the storage record', () => {
    const src = source(36, 42, (x, y) => [x * 7, y * 6, (x + y) * 3])
    const grid = avatarFromPixels(src, { levels: false, vignette: 0 })
    const rec = toAvatarRecord(grid)
    expect(rec.v).toBe(1)
    expect(rec.pixels).toHaveLength(36 * 42 * 6)
    expect(fromAvatarRecord(rec)).toEqual(grid)
  })

  it('rejects anything that is not a valid record', () => {
    expect(fromAvatarRecord(null)).toBeNull()
    expect(fromAvatarRecord('nope')).toBeNull()
    expect(fromAvatarRecord({ v: 2, w: 1, h: 1, pixels: 'ffffff' })).toBeNull()
    expect(fromAvatarRecord({ v: 1, w: 2, h: 1, pixels: 'ffffff' })).toBeNull() // wrong length
    expect(fromAvatarRecord({ v: 1, w: 1, h: 1, pixels: 'zzzzzz' })).toBeNull() // not hex
    expect(fromAvatarRecord({ v: 1, w: 1000, h: 1, pixels: '' })).toBeNull() // absurd size
    expect(fromAvatarRecord({ v: 1, w: 1, h: 1, pixels: 'c9a24b' })).toEqual({ w: 1, h: 1, cells: ['#c9a24b'] })
  })
})
