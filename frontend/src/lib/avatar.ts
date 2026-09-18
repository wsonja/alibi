/**
 * Photo → pixel avatar (the player's detective, drawn in the suspects' style — DESIGN §6).
 *
 * Pure functions, no DOM: the capture component (components/avatar/AvatarCapture.tsx) owns the camera and hands
 * over RGBA pixels; this file turns them into a PortraitGrid in the suspects' palette so the same renderers
 * (renderToCanvas / gridRuns in pixelPortrait.ts) draw it. Only the tiny quantised grid is ever kept — the photo
 * itself is discarded the moment it has been sampled.
 */
import type { PortraitGrid } from './pixelPortrait'

/** 6:7 like the suspect portraits (24×28), but half again as fine so a real face still reads. */
export const AVATAR_W = 36
export const AVATAR_H = 42

/** RGBA pixels, row-major — the shape of `ImageData`. */
export interface RgbaSource {
  width: number
  height: number
  data: ArrayLike<number>
}

/**
 * The colours the suspect painter uses (skin, hair, eyes, its neutrals) plus a few garment and backdrop tones.
 * Quantising a photo onto this warm, lamplit range is what makes the avatar sit next to the cast.
 */
export const AVATAR_PALETTE: readonly string[] = [
  // skin — base / shade / light / blush per tone (fair, warm, olive, brown, dark)
  '#f4dcc4', '#d9b79a', '#fbeee0', '#e8a89a',
  '#ebc29c', '#c9996f', '#f5d9bb', '#dd9078',
  '#d4ae80', '#b08a5a', '#e4c59c', '#cc8a6a',
  '#a9714b', '#845436', '#c08a63', '#b9694f',
  '#6b4530', '#4e2f20', '#855a41', '#8a4a3a',
  // hair — base / shade / light (black, brown, grey, white, blonde, red)
  '#1e1712', '#100b08', '#3a2e26',
  '#5a3a22', '#3d2716', '#7a5334',
  '#9a9a94', '#6f6f6a', '#c2c2bb',
  '#e8e4da', '#bdb8ad', '#fffdf6',
  '#d9b466', '#b08f45', '#f0d48a',
  '#a8442a', '#7a2e1b', '#cf6a3f',
  // eyes
  '#3b6fb6', '#4f8a4a', '#77828a', '#7a5a2e',
  // the painter's neutrals: outline, eye white, mouth, white, gold, pearl
  '#17100b', '#f8f4ea', '#3a1c1c', '#f4efe4', '#c9a24b', '#f3efe6', '#cfc8ba',
  // garments
  '#14110f', '#2a2622', '#6f6246', '#5a4e37', '#1a1613', '#2b3a5c', '#3f5a8a', '#4a6b3f', '#7e1414', '#9c1c1c', '#5c3a6e',
  // backdrop tones (lacquer, wood) so dark corners quantise cleanly
  '#15100c', '#2a1610', '#3b2116', '#5a331c',
]

// ---------------------------------------------------------------------------------------------
// Cropping
// ---------------------------------------------------------------------------------------------

export interface CropRect {
  sx: number
  sy: number
  sw: number
  sh: number
}

/** Portion of the frame height the crop covers (a 6:7 box centred in the frame). */
export const CROP_FRACTION = 0.82

/** The largest centred 6:7 box covering CROP_FRACTION of the frame height (or the full width if that is narrower). */
export function cropRect(width: number, height: number, fraction = CROP_FRACTION): CropRect {
  let sh = height * fraction
  let sw = (sh * AVATAR_W) / AVATAR_H
  if (sw > width) {
    sw = width
    sh = (sw * AVATAR_H) / AVATAR_W
  }
  return { sx: (width - sw) / 2, sy: (height - sh) / 2, sw, sh }
}

// ---------------------------------------------------------------------------------------------
// Sampling and tone
// ---------------------------------------------------------------------------------------------

function clamp255(v: number): number {
  return v < 0 ? 0 : v > 255 ? 255 : v
}

/** Box-filter the RGBA source down to w×h cells. Returns RGB triplets (row-major, 3 floats per cell). */
export function sampleColors(src: RgbaSource, w = AVATAR_W, h = AVATAR_H): Float32Array {
  const out = new Float32Array(w * h * 3)
  const { width: sw, height: sh, data } = src
  if (sw <= 0 || sh <= 0) return out
  for (let gy = 0; gy < h; gy++) {
    const y0 = Math.floor((gy * sh) / h)
    const y1 = Math.min(sh, Math.max(y0 + 1, Math.floor(((gy + 1) * sh) / h)))
    for (let gx = 0; gx < w; gx++) {
      const x0 = Math.floor((gx * sw) / w)
      const x1 = Math.min(sw, Math.max(x0 + 1, Math.floor(((gx + 1) * sw) / w)))
      let r = 0
      let g = 0
      let b = 0
      let n = 0
      for (let y = y0; y < y1; y++) {
        for (let x = x0; x < x1; x++) {
          const i = (y * sw + x) * 4
          r += data[i] ?? 0
          g += data[i + 1] ?? 0
          b += data[i + 2] ?? 0
          n++
        }
      }
      const o = (gy * w + gx) * 3
      if (n) {
        out[o] = r / n
        out[o + 1] = g / n
        out[o + 2] = b / n
      }
    }
  }
  return out
}

/**
 * Stretch the tones so the 2nd–98th luminance percentiles span the full range — webcam frames are often flat and
 * grey, and a flat face quantises to a single skin swatch. Near-uniform input (a lens cap, a wall) is left alone.
 */
export function autoLevels(rgb: Float32Array, lo = 0.02, hi = 0.98): Float32Array {
  const n = Math.floor(rgb.length / 3)
  const out = new Float32Array(rgb.length)
  if (n === 0) return out
  const lum = new Float32Array(n)
  for (let i = 0; i < n; i++) lum[i] = 0.299 * (rgb[i * 3] ?? 0) + 0.587 * (rgb[i * 3 + 1] ?? 0) + 0.114 * (rgb[i * 3 + 2] ?? 0)
  const sorted = Float32Array.from(lum).sort()
  const min = sorted[Math.floor(lo * (n - 1))] ?? 0
  const max = sorted[Math.floor(hi * (n - 1))] ?? 255
  const range = max - min
  if (range < 8) {
    out.set(rgb)
    return out
  }
  const k = 255 / range
  for (let i = 0; i < rgb.length; i++) out[i] = clamp255(((rgb[i] ?? 0) - min) * k)
  return out
}

/** Darken towards the corners (lamplight), so the frame reads like the suspects' tinted discs. */
export function vignette(rgb: Float32Array, w: number, h: number, strength = 0.3): Float32Array {
  const out = new Float32Array(rgb.length)
  const cx = (w - 1) / 2
  const cy = (h - 1) / 2
  const rmax = Math.hypot(cx, cy) || 1
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const d = Math.hypot(x - cx, y - cy) / rmax
      const k = 1 - strength * d * d
      const o = (y * w + x) * 3
      out[o] = (rgb[o] ?? 0) * k
      out[o + 1] = (rgb[o + 1] ?? 0) * k
      out[o + 2] = (rgb[o + 2] ?? 0) * k
    }
  }
  return out
}

// ---------------------------------------------------------------------------------------------
// Quantisation
// ---------------------------------------------------------------------------------------------

interface Swatch {
  hex: string
  r: number
  g: number
  b: number
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

const swatchCache = new WeakMap<readonly string[], Swatch[]>()

function swatches(palette: readonly string[]): Swatch[] {
  let s = swatchCache.get(palette)
  if (!s) {
    s = palette.map((hex) => {
      const [r, g, b] = hexToRgb(hex)
      return { hex: hex.toLowerCase(), r, g, b }
    })
    swatchCache.set(palette, s)
  }
  return s
}

/** Nearest palette colour by the "redmean" weighted distance (cheap, perceptually decent). */
export function nearestColor(r: number, g: number, b: number, palette: readonly string[] = AVATAR_PALETTE): string {
  let best = palette[0]?.toLowerCase() ?? '#000000'
  let bestD = Infinity
  for (const s of swatches(palette)) {
    const rm = (r + s.r) / 2
    const dr = r - s.r
    const dg = g - s.g
    const db = b - s.b
    const d = (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db
    if (d < bestD) {
      bestD = d
      best = s.hex
    }
  }
  return best
}

/** Map every cell onto the palette. */
export function quantize(rgb: Float32Array, w: number, h: number, palette: readonly string[] = AVATAR_PALETTE): PortraitGrid {
  const cells: (string | null)[] = new Array<string | null>(w * h).fill(null)
  for (let i = 0; i < w * h; i++) cells[i] = nearestColor(rgb[i * 3] ?? 0, rgb[i * 3 + 1] ?? 0, rgb[i * 3 + 2] ?? 0, palette)
  return { w, h, cells }
}

export interface AvatarOptions {
  w?: number
  h?: number
  /** auto-levels on (default true) */
  levels?: boolean
  /** corner darkening 0..1 (default 0.3; 0 = off) */
  vignette?: number
  palette?: readonly string[]
}

/** The whole pipeline: sample → levels → vignette → palette. Deterministic for the same pixels. */
export function avatarFromPixels(src: RgbaSource, opts: AvatarOptions = {}): PortraitGrid {
  const w = opts.w ?? AVATAR_W
  const h = opts.h ?? AVATAR_H
  let rgb = sampleColors(src, w, h)
  if (opts.levels !== false) rgb = autoLevels(rgb)
  const v = opts.vignette ?? 0.3
  if (v > 0) rgb = vignette(rgb, w, h, v)
  return quantize(rgb, w, h, opts.palette ?? AVATAR_PALETTE)
}

// ---------------------------------------------------------------------------------------------
// Persistence (localStorage record; store/avatar.ts)
// ---------------------------------------------------------------------------------------------

export interface AvatarRecord {
  v: 1
  w: number
  h: number
  /** 6 lowercase hex digits per cell, row-major */
  pixels: string
}

const HEX6 = /^#?[0-9a-f]{6}$/i

/** Compact record for storage (~9 KB for the default grid). Transparent cells are stored as black. */
export function toAvatarRecord(grid: PortraitGrid): AvatarRecord {
  let pixels = ''
  for (let i = 0; i < grid.w * grid.h; i++) {
    const c = grid.cells[i]
    pixels += c && HEX6.test(c) ? c.replace('#', '').toLowerCase() : '000000'
  }
  return { v: 1, w: grid.w, h: grid.h, pixels }
}

/** Validate a stored record (any shape may come back from localStorage) and rebuild the grid; null when unusable. */
export function fromAvatarRecord(raw: unknown): PortraitGrid | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Partial<AvatarRecord>
  if (r.v !== 1) return null
  const w = r.w
  const h = r.h
  if (!Number.isInteger(w) || !Number.isInteger(h) || (w as number) < 1 || (h as number) < 1 || (w as number) > 256 || (h as number) > 256) return null
  const pixels = r.pixels
  if (typeof pixels !== 'string' || pixels.length !== (w as number) * (h as number) * 6 || !/^[0-9a-f]*$/.test(pixels)) return null
  const cells: (string | null)[] = []
  for (let i = 0; i < pixels.length; i += 6) cells.push(`#${pixels.slice(i, i + 6)}`)
  return { w: w as number, h: h as number, cells }
}
