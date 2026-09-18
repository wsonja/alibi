/**
 * Procedural pixel-art portraits (docs/DESIGN.md §6).
 *
 * A 24×28 grid, deterministic from a seed (the suspect id) and traits parsed from the public `portrait_prompt`.
 * Six expression variants. Pure functions — no DOM — so this file is unit-testable; `renderToCanvas` / `gridToSvg`
 * are the only places that touch a canvas/SVG string, and the React wrapper lives in components/portrait.
 */

export const GRID_W = 24
export const GRID_H = 28

export type PortraitEmotion = 'neutral' | 'nervous' | 'angry' | 'smug' | 'sad' | 'afraid'
export const PORTRAIT_EMOTIONS: readonly PortraitEmotion[] = ['neutral', 'nervous', 'angry', 'smug', 'sad', 'afraid']

export type HairColor = 'black' | 'brown' | 'grey' | 'white' | 'blonde' | 'red'
export type HairStyle = 'short' | 'slicked' | 'bun' | 'curls' | 'long' | 'bob' | 'bald'
export type Headwear = 'none' | 'cap' | 'fedora' | 'bowler' | 'cloche'
export type SkinTone = 'fair' | 'warm' | 'olive' | 'brown' | 'dark'
export type Clothing =
  | 'dinner'
  | 'tweed'
  | 'evening'
  | 'apron'
  | 'military'
  | 'suit'
  | 'dress'
  | 'hoodie'
  | 'blouse'
  | 'labcoat'
  | 'cardigan'
  | 'default'
export type AgeBand = 'young' | 'middle' | 'old'
export type EyeColor = 'dark' | 'blue' | 'green' | 'grey' | 'hazel'
export type Presentation = 'feminine' | 'masculine' | 'unknown'

export interface PortraitTraits {
  hairColor: HairColor
  hairStyle: HairStyle
  greyTemples: boolean
  headwear: Headwear
  skin: SkinTone
  spectacles: boolean
  monocle: boolean
  moustache: boolean
  beard: boolean
  pearls: boolean
  earrings: boolean
  cigar: boolean
  clothing: Clothing
  smile: boolean
  tired: boolean
  sharpEyes: boolean
  cold: boolean
  age: AgeBand
  eyeColor: EyeColor
  presentation: Presentation
  /** whether the prompt mentioned hair colour explicitly (else the seed picks) */
  hairColorExplicit: boolean
  hairStyleExplicit: boolean
}

export interface PortraitGrid {
  w: number
  h: number
  /** row-major, `null` = transparent */
  cells: (string | null)[]
}

export interface BuildOptions {
  traits: PortraitTraits
  emotion?: PortraitEmotion
  seed: string
  /** eyes closed this frame */
  blink?: boolean
  /** draw the emotion-tinted disc behind the head (default true) */
  disc?: boolean
}

// ---------------------------------------------------------------------------------------------
// Deterministic randomness
// ---------------------------------------------------------------------------------------------

export function hashString(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// ---------------------------------------------------------------------------------------------
// Trait parsing
// ---------------------------------------------------------------------------------------------

const FEMININE = /\b(woman|lady|girl|she|her|hers|maid|housemaid|actress|widow|wife|daughter|mother|aunt|nurse|governess|heiress|duchess|countess|mrs|miss|ms|madam|matron|queen|princess)\b/i
const MASCULINE = /\b(man|gentleman|businessman|doctor|he|him|his|boy|butler|colonel|captain|major|mr|sir|lord|father|uncle|son|husband|footman|valet|chauffeur|professor|king|prince|duke|earl|baron)\b/i

export function parseTraits(prompt: string | null | undefined): PortraitTraits {
  const p = (prompt ?? '').toLowerCase()
  const has = (re: RegExp) => re.test(p)

  const presentation: Presentation = has(FEMININE) && !has(MASCULINE) ? 'feminine' : has(MASCULINE) && !has(FEMININE) ? 'masculine' : has(FEMININE) ? 'feminine' : has(MASCULINE) ? 'masculine' : 'unknown'

  // hair colour ------------------------------------------------------------------------------
  let hairColor: HairColor = 'brown'
  let hairColorExplicit = true
  const H = '(hair|haired|curls|locks|bob|bun|mane|tresses|mop|fringe|waves)'
  if (has(new RegExp(`\\b(black|dark|raven|jet|ebony)(-| )?${H}\\b`))) hairColor = 'black'
  else if (has(/\b(white|snow(-| )?white|silver)(-| )?(hair|haired)\b/) || has(/\bwhite(-| )?haired\b/)) hairColor = 'white'
  else if (has(/\b(grey|gray|silver|silvered|greying|graying|salt(-| )and(-| )pepper)\b/) && !has(/grey at the temples|gray at the temples|greying at the temples/)) hairColor = 'grey'
  else if (has(/\b(blonde?|fair(-| )?haired|fair hair|golden(-| )?hair|flaxen|platinum|straw(-| )?colou?red)\b/)) hairColor = 'blonde'
  else if (has(new RegExp(`\\b(red(-| )?(${H.slice(1, -1)}|head|headed)|ginger|auburn|copper|titian|strawberry)\\b`))) hairColor = 'red'
  else if (has(new RegExp(`\\b(brown|chestnut|brunette|mousy|sandy|tawny)(-| )?${H}?\\b`))) hairColor = 'brown'
  else if (has(/\bblack hair\b|\bdark hair\b/)) hairColor = 'black'
  else hairColorExplicit = false

  const greyTemples = has(/(grey|gray|greying|graying|silver) at the temples|temples? (gone |going )?(grey|gray)|distinguished grey/)

  // hair style -------------------------------------------------------------------------------
  let hairStyle: HairStyle = presentation === 'feminine' ? 'bob' : 'short'
  let hairStyleExplicit = true
  if (has(/\b(brilliantined|slicked|slick|pomaded|pomade|side(-| )?part(ed)?|combed back|oiled)\b/)) hairStyle = 'slicked'
  else if (has(/\b(pinned(-| )up|pinned|bun|chignon|updo|up-do|swept up|coiled)\b/)) hairStyle = 'bun'
  else if (has(/\b(curly|curls|curl|tousled|unruly|wild hair|frizzy|mop of)\b/)) hairStyle = 'curls'
  else if (has(/\b(long hair|long(-| )haired|flowing|loose hair|braid|plait|waist(-| )length|hair down)\b/)) hairStyle = 'long'
  else if (has(/\b(bald|balding|shaven(-| )head|shaved head|hairless)\b/)) hairStyle = 'bald'
  else if (has(/\b(bob|bobbed|cropped|shingled|marcel)\b/)) hairStyle = 'bob'
  else if (has(/\b(short hair|close(-| )cropped|crew cut|neat hair|short(-| )haired)\b/)) hairStyle = 'short'
  else hairStyleExplicit = false

  // headwear ---------------------------------------------------------------------------------
  let headwear: Headwear = 'none'
  if (has(/\b(cap|housemaid|maid|nurse|mob cap|lace cap)\b/) && !has(/\b(flat cap|peaked cap|cloth cap)\b/)) headwear = 'cap'
  else if (has(/\b(fedora|trilby|homburg|hat|flat cap|peaked cap|cloth cap|panama)\b/) && !has(/\bcloche\b|\bbowler\b/)) headwear = 'fedora'
  else if (has(/\bbowler\b/)) headwear = 'bowler'
  else if (has(/\bcloche\b/)) headwear = 'cloche'

  // skin -------------------------------------------------------------------------------------
  let skin: SkinTone = 'warm'
  if (has(/\b(dark(-| )skin(ned)?|black skin|deep brown skin|ebony skin|very dark)\b/)) skin = 'dark'
  else if (has(/\b(brown(-| )skin(ned)?|light brown skin|bronze|mahogany skin)\b/)) skin = 'brown'
  else if (has(/\b(olive|tanned|tan skin|sun(-| )?browned|mediterranean|weather(-| )?beaten)\b/)) skin = 'olive'
  else if (has(/\b(pale|porcelain|ivory|fair(-| )?skin(ned)?|fair complexion|milky|wan|pallid|ashen)\b/) || (has(/\bfair\b/) && !has(/fair(-| )?hair/))) skin = 'fair'

  // accessories / features -------------------------------------------------------------------
  const spectacles = has(/\b(spectacles|glasses|pince-nez|bespectacled|eyeglasses)\b/) || has(/\b(doctor|professor|clerk|librarian|accountant|scholar|solicitor|bookkeeper|physician|surgeon)\b/)
  const monocle = has(/\bmonocle\b/)
  const moustache = has(/\b(moustache|mustache|moustached|mustached|whiskers|handlebar)\b/)
  const beard = has(/\b(beard|bearded|goatee|full beard|stubble)\b/)
  const pearls = has(/\bpearls?\b/)
  const earrings = has(/\bearrings?\b/) || (pearls && presentation === 'feminine')
  const cigar = has(/\b(cigar|cigars|cigarette|cheroot|pipe|smoking|smokes)\b/)
  const smile = has(/\b(smile|smiling|smirk|grin|grinning|laugh|laughing|jovial|cheerful|genial|affable|easy|charming)\b/)
  const tired = has(/\b(tired|weary|exhausted|haggard|drawn|hollow|sleepless|worn)\b/)
  const sharpEyes = has(/\b(sharp|watchful|keen|piercing|narrow|shrewd|wary|alert|calculating)\b/)
  const cold = has(/\b(cold|composed|stern|severe|icy|haughty|imperious|unsmiling|austere|aloof|glacial)\b/)

  let eyeColor: EyeColor = 'dark'
  if (has(/\bblue(-| )?eye/)) eyeColor = 'blue'
  else if (has(/\bgreen(-| )?eye/)) eyeColor = 'green'
  else if (has(/\bgrey(-| )?eye|gray(-| )?eye/)) eyeColor = 'grey'
  else if (has(/\bhazel/)) eyeColor = 'hazel'

  // age --------------------------------------------------------------------------------------
  let age: AgeBand = 'middle'
  if (has(/\b(teen|teenage|student|twenties|twenty|young|youthful|early 20s|late 20s|20s|girl|boy|undergraduate|nineteen|eighteen)\b/)) age = 'young'
  else if (has(/\b(sixt(y|ies)|sevent(y|ies)|eight(y|ies)|elderly|old|aged|ancient|venerable|white(-| )?haired|60s|70s|80s)\b/)) age = 'old'
  else if (has(/\b(thirt(y|ies)|fort(y|ies)|fift(y|ies)|middle(-| )aged|30s|40s|50s|mid-forties|early forties|late forties)\b/)) age = 'middle'
  if (!hairColorExplicit && age === 'old') {
    hairColor = 'grey'
  }

  // clothing ---------------------------------------------------------------------------------
  let clothing: Clothing = 'default'
  if (has(/\bapron\b/)) clothing = 'apron'
  else if (has(/\b(tweed|waistcoat|herringbone|houndstooth)\b/)) clothing = 'tweed' // tweed under a jacket draws both
  else if (has(/\b(dinner jacket|tuxedo|tails|white tie|black tie|dinner suit)\b/)) clothing = 'dinner'
  else if (has(/\b(evening dress|evening gown|gown|high-necked|high necked|silk dress|velvet dress|beaded)\b/)) clothing = 'evening'
  else if (has(/\b(military|uniform|khaki|regimental|officer|army|naval|navy)\b/)) clothing = 'military'
  else if (has(/\b(lab coat|labcoat|white coat|scrubs)\b/)) clothing = 'labcoat'
  else if (has(/\b(hoodie|sweatshirt|t-shirt|tee|tech bro|fleece)\b/)) clothing = 'hoodie'
  else if (has(/\b(cardigan|jumper|sweater|knit)\b/)) clothing = 'cardigan'
  else if (has(/\b(blouse|shawl|collar|lace)\b/) && presentation === 'feminine') clothing = 'blouse'
  else if (has(/\b(suit|pinstripe|three-piece|three piece|jacket|blazer|overcoat)\b/)) clothing = 'suit'
  else if (has(/\b(dress|frock|skirt)\b/)) clothing = 'dress'
  else if (presentation === 'feminine') clothing = 'dress'
  else if (presentation === 'masculine') clothing = 'suit'

  return {
    hairColor,
    hairStyle,
    greyTemples,
    headwear,
    skin,
    spectacles,
    monocle,
    moustache,
    beard,
    pearls,
    earrings,
    cigar,
    clothing,
    smile,
    tired,
    sharpEyes,
    cold,
    age,
    eyeColor,
    presentation,
    hairColorExplicit,
    hairStyleExplicit,
  }
}

/** One-line human summary, handy for alt text and tests. */
export function describeTraits(t: PortraitTraits): string {
  const bits: string[] = []
  if (t.headwear === 'cap') bits.push('a white cap')
  if (t.headwear === 'fedora') bits.push('a fedora')
  if (t.headwear === 'bowler') bits.push('a bowler hat')
  if (t.headwear === 'cloche') bits.push('a cloche hat')
  const style = t.hairStyle === 'bun' ? 'hair pinned up' : t.hairStyle === 'slicked' ? 'slicked hair' : t.hairStyle === 'curls' ? 'curly hair' : t.hairStyle === 'long' ? 'long hair' : t.hairStyle === 'bob' ? 'bobbed hair' : t.hairStyle === 'bald' ? 'a bald head' : 'short hair'
  bits.push(`${t.hairColor} ${style}${t.greyTemples ? ', grey at the temples' : ''}`)
  if (t.spectacles) bits.push('spectacles')
  if (t.monocle) bits.push('a monocle')
  if (t.moustache) bits.push('a moustache')
  if (t.beard) bits.push('a beard')
  if (t.pearls) bits.push('pearls')
  if (t.cigar) bits.push('a cigar')
  bits.push(`${t.clothing === 'default' ? 'plain' : t.clothing} clothes`)
  return bits.join(', ')
}

// ---------------------------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------------------------

const SKIN: Record<SkinTone, { base: string; shade: string; light: string; blush: string }> = {
  fair: { base: '#f4dcc4', shade: '#d9b79a', light: '#fbeee0', blush: '#e8a89a' },
  warm: { base: '#ebc29c', shade: '#c9996f', light: '#f5d9bb', blush: '#dd9078' },
  olive: { base: '#d4ae80', shade: '#b08a5a', light: '#e4c59c', blush: '#cc8a6a' },
  brown: { base: '#a9714b', shade: '#845436', light: '#c08a63', blush: '#b9694f' },
  dark: { base: '#6b4530', shade: '#4e2f20', light: '#855a41', blush: '#8a4a3a' },
}

const HAIR: Record<HairColor, { base: string; shade: string; light: string }> = {
  black: { base: '#1e1712', shade: '#100b08', light: '#3a2e26' },
  brown: { base: '#5a3a22', shade: '#3d2716', light: '#7a5334' },
  grey: { base: '#9a9a94', shade: '#6f6f6a', light: '#c2c2bb' },
  white: { base: '#e8e4da', shade: '#bdb8ad', light: '#fffdf6' },
  blonde: { base: '#d9b466', shade: '#b08f45', light: '#f0d48a' },
  red: { base: '#a8442a', shade: '#7a2e1b', light: '#cf6a3f' },
}

const EYE: Record<EyeColor, string> = {
  dark: '#1e1712',
  blue: '#3b6fb6',
  green: '#4f8a4a',
  grey: '#77828a',
  hazel: '#7a5a2e',
}

const EMOTION_TINT: Record<PortraitEmotion, string> = {
  neutral: '#6b7280',
  nervous: '#d97706',
  angry: '#dc2626',
  smug: '#7c3aed',
  sad: '#2563eb',
  afraid: '#0d9488',
}

const OUTLINE = '#17100b'
const EYE_WHITE = '#f8f4ea'
const MOUTH_DARK = '#3a1c1c'
const WHITE = '#f4efe4'
const GOLD = '#c9a24b'
const PEARL = '#f3efe6'
const PEARL_SHADE = '#cfc8ba'
const SWEAT = '#9cd3f0'
const SWEAT_LIGHT = '#d7f0fb'
const EMBER = '#e8602a'
const SMOKE = '#9a9a94'

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
function rgbToHex(r: number, g: number, b: number): string {
  const c = (v: number) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')
  return `#${c(r)}${c(g)}${c(b)}`
}
/** mix(a, b, t): t=0 → a, t=1 → b */
export function mix(a: string, b: string, t: number): string {
  const [ar, ag, ab] = hexToRgb(a)
  const [br, bg, bb] = hexToRgb(b)
  return rgbToHex(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t)
}

// ---------------------------------------------------------------------------------------------
// Grid builder
// ---------------------------------------------------------------------------------------------

class Painter {
  readonly cells: (string | null)[] = new Array<string | null>(GRID_W * GRID_H).fill(null)
  /** true where a figure (not background) pixel was painted — used for the outline */
  readonly figure: boolean[] = new Array<boolean>(GRID_W * GRID_H).fill(false)

  px(x: number, y: number, color: string, isFigure = true): void {
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return
    const i = y * GRID_W + x
    this.cells[i] = color
    if (isFigure) this.figure[i] = true
  }
  row(y: number, x0: number, x1: number, color: string, isFigure = true): void {
    for (let x = x0; x <= x1; x++) this.px(x, y, color, isFigure)
  }
  rect(x0: number, y0: number, x1: number, y1: number, color: string, isFigure = true): void {
    for (let y = y0; y <= y1; y++) this.row(y, x0, x1, color, isFigure)
  }
  get(x: number, y: number): string | null {
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return null
    return this.cells[y * GRID_W + x] ?? null
  }
  isFigure(x: number, y: number): boolean {
    if (x < 0 || y < 0 || x >= GRID_W || y >= GRID_H) return false
    return this.figure[y * GRID_W + x] ?? false
  }
}

/** Head row extents (inclusive) by jaw variant. Row → [x0, x1]. */
function headRows(jaw: 'round' | 'square' | 'narrow'): Record<number, [number, number]> {
  const rows: Record<number, [number, number]> = {
    5: [8, 15],
    6: [7, 16],
    7: [6, 17],
    8: [5, 18],
    9: [5, 18],
    10: [5, 18],
    11: [5, 18],
    12: [5, 18],
    13: [5, 18],
    14: [5, 18],
    15: [5, 18],
    16: [5, 18],
    17: [5, 18],
    18: [6, 17],
    19: [7, 16],
    20: [8, 15],
  }
  if (jaw === 'square') {
    rows[18] = [6, 17]
    rows[19] = [6, 17]
    rows[20] = [7, 16]
  } else if (jaw === 'narrow') {
    rows[17] = [6, 17]
    rows[18] = [7, 16]
    rows[19] = [8, 15]
    rows[20] = [9, 14]
  }
  return rows
}

function paintTorso(p: Painter, t: PortraitTraits, skin: (typeof SKIN)[SkinTone], rnd: () => number): void {
  // neck
  p.rect(10, 21, 13, 22, skin.shade)
  p.px(11, 21, skin.base)
  p.px(12, 21, skin.base)

  const torso = (base: string) => {
    p.row(23, 7, 16, base)
    p.row(24, 5, 18, base)
    p.row(25, 3, 20, base)
    p.row(26, 2, 21, base)
    p.row(27, 2, 21, base)
  }
  const shirtV = (color: string) => {
    p.row(23, 10, 13, color)
    p.px(11, 24, color)
    p.px(12, 24, color)
  }
  const lapels = (color: string) => {
    p.px(9, 24, color)
    p.px(8, 25, color)
    p.px(7, 26, color)
    p.px(14, 24, color)
    p.px(15, 25, color)
    p.px(16, 26, color)
  }

  switch (t.clothing) {
    case 'dinner': {
      torso('#14110f')
      shirtV(WHITE)
      lapels('#2a2622')
      // bow tie
      p.row(24, 10, 13, '#0b0908')
      p.px(11, 24, '#1e1a17')
      p.px(12, 24, '#1e1a17')
      break
    }
    case 'tweed': {
      torso('#6f6246')
      for (let y = 23; y <= 27; y++)
        for (let x = 2; x <= 21; x++) if (p.get(x, y) === '#6f6246' && (x + y) % 2 === 0) p.px(x, y, '#5a4e37')
      // dark jacket over the waistcoat (Crane: "tweed waistcoat under a dinner jacket")
      p.row(25, 3, 8, '#1a1613')
      p.row(25, 15, 20, '#1a1613')
      p.row(26, 2, 8, '#1a1613')
      p.row(26, 15, 21, '#1a1613')
      p.row(27, 2, 8, '#1a1613')
      p.row(27, 15, 21, '#1a1613')
      p.row(24, 5, 8, '#1a1613')
      p.row(24, 15, 18, '#1a1613')
      shirtV(WHITE)
      p.px(11, 25, '#7e1414')
      p.px(12, 25, '#7e1414')
      p.px(11, 26, '#7e1414')
      p.px(12, 26, '#7e1414')
      break
    }
    case 'evening': {
      const velvet = rnd() < 0.5 ? '#3a1a4a' : '#1f3a2a'
      torso(velvet)
      // high neck: cover the neck
      p.rect(9, 21, 14, 22, velvet)
      p.row(23, 7, 16, mix(velvet, '#ffffff', 0.12))
      p.px(12, 24, GOLD) // brooch
      break
    }
    case 'apron': {
      torso('#2e2a33')
      p.row(23, 9, 14, WHITE) // white collar
      p.rect(9, 24, 14, 27, '#f0ebe0') // apron bib
      p.px(8, 24, '#f0ebe0')
      p.px(15, 24, '#f0ebe0')
      p.px(9, 25, '#dcd6c8')
      p.px(14, 25, '#dcd6c8')
      break
    }
    case 'military': {
      torso('#6b6a3e')
      p.row(23, 8, 15, '#4f4e2c')
      p.px(12, 24, GOLD)
      p.px(12, 26, GOLD)
      p.px(5, 24, GOLD)
      p.px(18, 24, GOLD)
      break
    }
    case 'labcoat': {
      torso('#e9e6dc')
      shirtV('#8fb3d9')
      lapels('#cfcabd')
      break
    }
    case 'hoodie': {
      torso('#3a4a5a')
      p.row(23, 8, 15, '#2c3a47')
      p.px(10, 24, WHITE)
      p.px(13, 24, WHITE)
      p.px(10, 25, WHITE)
      p.px(13, 25, WHITE)
      break
    }
    case 'cardigan': {
      torso('#6b4a3a')
      shirtV('#efe6d4')
      p.px(12, 25, '#3d2716')
      p.px(12, 27, '#3d2716')
      break
    }
    case 'blouse': {
      torso('#cbc1ad')
      p.row(23, 9, 14, WHITE)
      p.px(12, 24, '#7e1414')
      break
    }
    case 'dress': {
      const dress = rnd() < 0.5 ? '#5a2a3a' : '#2a3a5a'
      torso(dress)
      p.row(23, 9, 14, skin.base) // round neckline
      break
    }
    case 'suit':
    default: {
      const suit = rnd() < 0.5 ? '#3b332b' : '#2f3540'
      torso(suit)
      shirtV(WHITE)
      lapels(mix(suit, '#ffffff', 0.12))
      p.px(11, 24, '#7e1414')
      p.px(12, 24, '#7e1414')
      p.px(11, 25, '#7e1414')
      p.px(12, 25, '#7e1414')
      break
    }
  }
}

function paintHair(p: Painter, t: PortraitTraits, rows: Record<number, [number, number]>, rnd: () => number): void {
  const h = HAIR[t.hairColor]
  const capRows = (from: number, to: number) => {
    for (let y = from; y <= to; y++) {
      const r = rows[y]
      if (r) p.row(y, r[0], r[1], h.base)
    }
  }
  const temples = () => {
    p.row(9, 5, 6, h.base)
    p.row(9, 17, 18, h.base)
  }
  const sideburns = (to: number) => {
    p.rect(5, 10, 5, to, h.base)
    p.rect(18, 10, 18, to, h.base)
  }
  const underBrim = t.headwear === 'fedora' || t.headwear === 'bowler'

  switch (t.hairStyle) {
    case 'bald': {
      p.row(7, 5, 6, h.base)
      p.row(7, 17, 18, h.base)
      p.row(8, 5, 5, h.base)
      p.row(8, 18, 18, h.base)
      sideburns(11)
      break
    }
    case 'slicked': {
      if (!underBrim) {
        p.row(4, 9, 14, h.base)
        capRows(5, 8)
        // swept fringe on one side, shine on the other
        const left = rnd() < 0.5
        if (left) {
          p.row(9, 5, 8, h.base)
          p.px(9, 9, h.base)
          p.px(14, 5, h.light)
          p.px(15, 5, h.light)
          p.px(16, 6, h.light)
        } else {
          p.row(9, 15, 18, h.base)
          p.px(14, 9, h.base)
          p.px(8, 5, h.light)
          p.px(9, 5, h.light)
          p.px(7, 6, h.light)
        }
      } else {
        capRows(7, 8)
      }
      temples()
      sideburns(11)
      break
    }
    case 'bun': {
      if (!underBrim && t.headwear !== 'cap' && t.headwear !== 'cloche') {
        p.row(2, 10, 13, h.base)
        p.row(3, 9, 14, h.base)
        p.px(11, 2, h.light)
        p.row(4, 8, 15, h.base)
        capRows(5, 8)
        p.px(11, 5, h.shade)
        p.px(12, 5, h.shade)
      } else {
        capRows(7, 8)
      }
      temples()
      // hair framing the face
      p.rect(5, 10, 5, 12, h.base)
      p.rect(18, 10, 18, 12, h.base)
      p.px(6, 10, h.base)
      p.px(17, 10, h.base)
      break
    }
    case 'curls': {
      if (!underBrim) {
        p.row(4, 7, 16, h.base)
        for (const x of [8, 10, 12, 14, 15]) p.px(x, 3, h.base)
        p.px(6, 5, h.base)
        p.px(17, 5, h.base)
        p.px(4, 8, h.base)
        p.px(19, 8, h.base)
        capRows(5, 8)
        p.px(9, 4, h.light)
        p.px(13, 4, h.light)
      } else {
        capRows(7, 8)
      }
      temples()
      p.px(4, 10, h.base)
      p.px(19, 10, h.base)
      p.px(4, 12, h.base)
      p.px(19, 12, h.base)
      sideburns(13)
      break
    }
    case 'long': {
      if (!underBrim) {
        p.row(4, 8, 15, h.base)
        capRows(5, 8)
      } else capRows(7, 8)
      temples()
      p.rect(4, 9, 5, 20, h.base)
      p.rect(18, 9, 19, 20, h.base)
      p.rect(4, 21, 6, 23, h.base)
      p.rect(17, 21, 19, 23, h.base)
      p.px(4, 12, h.light)
      p.px(19, 12, h.light)
      break
    }
    case 'bob': {
      if (!underBrim) {
        p.row(4, 8, 15, h.base)
        capRows(5, 8)
        if (t.headwear !== 'cloche') p.row(9, 6, 17, h.base) // fringe
      } else capRows(7, 8)
      temples()
      p.rect(4, 9, 5, 16, h.base)
      p.rect(18, 9, 19, 16, h.base)
      p.px(4, 17, h.base)
      p.px(19, 17, h.base)
      p.px(9, 5, h.light)
      break
    }
    case 'short':
    default: {
      if (!underBrim) {
        p.row(4, 8, 15, h.base)
        capRows(5, 8)
        p.px(10, 4, h.light)
      } else capRows(7, 8)
      temples()
      sideburns(11)
      break
    }
  }

  if (t.greyTemples || (t.age === 'old' && t.hairStyle !== 'bald')) {
    const g = HAIR.grey.base
    for (const [x, y] of [
      [5, 9],
      [6, 9],
      [5, 10],
      [5, 11],
      [18, 9],
      [17, 9],
      [18, 10],
      [18, 11],
    ] as const) {
      if (p.get(x, y) === h.base) p.px(x, y, g)
    }
  }
}

function paintHeadwear(p: Painter, t: PortraitTraits, rnd: () => number): void {
  const h = HAIR[t.hairColor]
  switch (t.headwear) {
    case 'cap': {
      p.row(3, 8, 15, WHITE)
      p.row(4, 7, 16, WHITE)
      p.row(5, 6, 17, WHITE)
      p.row(6, 6, 17, '#e4ded0')
      for (let x = 6; x <= 17; x++) p.px(x, 7, x % 2 === 0 ? WHITE : h.base)
      p.px(9, 4, '#fffdf6')
      break
    }
    case 'fedora': {
      const hat = rnd() < 0.5 ? '#3b3630' : '#4a3220'
      const band = hat === '#3b3630' ? '#1f1c19' : '#7e1414'
      p.row(1, 8, 15, hat)
      p.rect(7, 2, 16, 4, hat)
      p.row(2, 8, 15, mix(hat, '#ffffff', 0.15)) // crown crease highlight
      p.row(5, 7, 16, band)
      p.row(6, 3, 20, hat)
      p.px(3, 6, mix(hat, '#ffffff', 0.18))
      p.px(20, 6, mix(hat, '#ffffff', 0.18))
      break
    }
    case 'bowler': {
      const hat = '#1a1613'
      p.row(2, 9, 14, hat)
      p.rect(8, 3, 15, 4, hat)
      p.row(5, 8, 15, '#2c2622')
      p.row(6, 5, 18, hat)
      p.px(10, 3, '#3a332e')
      break
    }
    case 'cloche': {
      const hat = rnd() < 0.5 ? '#7a2e3a' : '#2a4a5a'
      p.row(2, 9, 14, hat)
      p.row(3, 7, 16, hat)
      p.rect(5, 4, 18, 8, hat)
      p.row(9, 4, 19, mix(hat, '#000000', 0.25))
      p.px(15, 6, GOLD)
      p.px(16, 6, mix(hat, '#ffffff', 0.35))
      break
    }
    default:
      break
  }
}

function skinFor(t: PortraitTraits, emotion: PortraitEmotion) {
  const skinBase = SKIN[t.skin]
  const pale = emotion === 'afraid'
  return pale
    ? { base: mix(skinBase.base, '#ffffff', 0.32), shade: mix(skinBase.shade, '#ffffff', 0.25), light: mix(skinBase.light, '#ffffff', 0.3), blush: skinBase.blush }
    : skinBase
}

/** Skin: head, ears, jaw shading. Painted before the hair so hats and fringes sit on top of it. */
function paintHead(p: Painter, t: PortraitTraits, emotion: PortraitEmotion, rows: Record<number, [number, number]>): void {
  const skin = skinFor(t, emotion)
  // head + ears
  for (let y = 5; y <= 20; y++) {
    const r = rows[y]
    if (r) p.row(y, r[0], r[1], skin.base)
  }
  p.rect(4, 12, 4, 13, skin.base)
  p.rect(19, 12, 19, 13, skin.base)
  p.px(4, 13, skin.shade)
  p.px(19, 13, skin.shade)
  // cheek/jaw shading
  const chinRow = rows[20]
  if (chinRow) p.row(20, chinRow[0], chinRow[1], skin.shade)
  const jawRow = rows[19]
  if (jawRow) {
    p.px(jawRow[0], 19, skin.shade)
    p.px(jawRow[1], 19, skin.shade)
  }
  // forehead highlight
  p.px(9, 10, skin.light)
  p.px(10, 9, skin.light)

  // bald shine
  if (t.hairStyle === 'bald' && t.headwear === 'none') {
    p.px(10, 6, skin.light)
    p.px(11, 6, skin.light)
  }

}

/** Brows, eyes, nose, mouth, facial hair, spectacles, earrings. Painted after hair/hats so raised brows stay visible. */
function paintFeatures(p: Painter, t: PortraitTraits, emotion: PortraitEmotion, blink: boolean, rows: Record<number, [number, number]>, rnd: () => number): void {
  const skin = skinFor(t, emotion)
  const h = HAIR[t.hairColor]
  const browColor = t.hairColor === 'white' || t.hairColor === 'blonde' ? HAIR.brown.shade : h.shade
  // ---- brows -----------------------------------------------------------------------------
  const brow = (pts: Array<[number, number]>) => pts.forEach(([x, y]) => p.px(x, y, browColor))
  switch (emotion) {
    case 'nervous':
      brow([
        [7, 9],
        [8, 9],
        [9, 8],
        [14, 8],
        [15, 9],
        [16, 9],
      ])
      break
    case 'angry':
      brow([
        [7, 9],
        [8, 10],
        [9, 11],
        [14, 11],
        [15, 10],
        [16, 9],
      ])
      break
    case 'smug':
      brow([
        [7, 9],
        [8, 9],
        [9, 9],
        [14, 10],
        [15, 10],
        [16, 10],
      ])
      break
    case 'sad':
      brow([
        [7, 11],
        [8, 10],
        [9, 9],
        [14, 9],
        [15, 10],
        [16, 11],
      ])
      break
    case 'afraid':
      brow([
        [7, 8],
        [8, 8],
        [9, 8],
        [14, 8],
        [15, 8],
        [16, 8],
      ])
      break
    default:
      brow([
        [7, 10],
        [8, 10],
        [9, 10],
        [14, 10],
        [15, 10],
        [16, 10],
      ])
  }

  // ---- eyes ------------------------------------------------------------------------------
  const pupil = EYE[t.eyeColor]
  const lid = skin.shade
  const eyeL = { x0: 7, x1: 9 }
  const eyeR = { x0: 14, x1: 16 }
  const drawEye = (e: { x0: number; x1: number }, pupilX: number, style: 'open' | 'wide' | 'half' | 'narrow') => {
    if (blink) {
      p.row(13, e.x0, e.x1, lid)
      return
    }
    if (style === 'wide') {
      p.rect(e.x0, 11, e.x1, 13, EYE_WHITE)
      p.px(pupilX, 12, pupil)
      return
    }
    if (style === 'narrow') {
      p.row(13, e.x0, e.x1, EYE_WHITE)
      p.px(pupilX, 13, pupil)
      p.row(12, e.x0, e.x1, lid)
      return
    }
    if (style === 'half') {
      p.row(12, e.x0, e.x1, lid)
      p.row(13, e.x0, e.x1, EYE_WHITE)
      p.px(pupilX, 13, pupil)
      return
    }
    p.rect(e.x0, 12, e.x1, 13, EYE_WHITE)
    p.px(pupilX, 12, pupil)
    p.px(pupilX, 13, pupil)
    p.px(pupilX, 12, mix(pupil, '#ffffff', 0.25))
  }
  let styleL: 'open' | 'wide' | 'half' | 'narrow' = t.sharpEyes ? 'narrow' : 'open'
  let styleR: 'open' | 'wide' | 'half' | 'narrow' = styleL
  let pupilL = 8
  let pupilR = 15
  switch (emotion) {
    case 'nervous':
      pupilL = 7
      pupilR = 14
      break
    case 'angry':
      styleL = 'narrow'
      styleR = 'narrow'
      break
    case 'smug':
      styleL = 'half'
      styleR = 'half'
      pupilL = 9
      pupilR = 16
      break
    case 'afraid':
      styleL = 'wide'
      styleR = 'wide'
      break
    default:
      break
  }
  drawEye(eyeL, pupilL, styleL)
  drawEye(eyeR, pupilR, styleR)

  // tired / age lines
  if (t.tired || t.age === 'old') {
    p.px(7, 14, skin.shade)
    p.px(8, 14, skin.shade)
    p.px(15, 14, skin.shade)
    p.px(16, 14, skin.shade)
  }
  if (t.age !== 'young') {
    p.px(6, 13, skin.shade)
    p.px(17, 13, skin.shade)
  }
  if (t.age === 'old') {
    p.px(6, 12, skin.shade)
    p.px(17, 12, skin.shade)
    p.row(9, 9, 14, skin.shade)
  }

  // ---- nose ------------------------------------------------------------------------------
  p.px(12, 14, skin.shade)
  p.px(11, 15, skin.shade)
  p.px(12, 15, skin.shade)

  // ---- mouth -----------------------------------------------------------------------------
  const lip = mix(skin.shade, '#b0604f', 0.45)
  const lipDark = mix(skin.shade, '#5a2a2a', 0.6)
  switch (emotion) {
    case 'nervous':
      p.px(10, 17, lip)
      p.px(11, 18, lip)
      p.px(12, 17, lip)
      p.px(13, 18, lip)
      break
    case 'angry':
      p.row(17, 9, 14, lipDark)
      p.px(6, 15, skin.blush)
      p.px(7, 15, skin.blush)
      p.px(16, 15, skin.blush)
      p.px(17, 15, skin.blush)
      break
    case 'smug':
      p.row(17, 10, 13, lip)
      p.px(14, 16, lip)
      break
    case 'sad':
      p.px(10, 18, lip)
      p.px(11, 17, lip)
      p.px(12, 17, lip)
      p.px(13, 18, lip)
      break
    case 'afraid':
      p.px(10, 17, lip)
      p.px(13, 17, lip)
      p.rect(11, 17, 12, 18, MOUTH_DARK)
      p.px(10, 18, lip)
      p.px(13, 18, lip)
      break
    default:
      if (t.smile) {
        p.row(17, 10, 13, lip)
        p.px(9, 16, lip)
        p.px(14, 16, lip)
      } else if (t.cold) {
        p.row(17, 10, 13, lipDark)
      } else {
        p.row(17, 10, 13, lip)
      }
  }

  // ---- facial hair -----------------------------------------------------------------------
  if (t.moustache) {
    p.row(16, 9, 14, h.base)
    p.px(8, 17, h.base)
    p.px(15, 17, h.base)
    p.px(11, 16, h.shade)
    p.px(12, 16, h.shade)
  }
  if (t.beard) {
    const r18 = rows[18]
    const r19 = rows[19]
    const r20 = rows[20]
    if (r18) p.row(18, r18[0], r18[1], h.base)
    if (r19) p.row(19, r19[0], r19[1], h.base)
    if (r20) p.row(20, r20[0], r20[1], h.base)
    p.row(21, 9, 14, h.base)
    p.rect(5, 15, 5, 17, h.base)
    p.rect(18, 15, 18, 17, h.base)
    p.px(11, 19, h.light)
    if (emotion === 'afraid') p.rect(11, 18, 12, 18, MOUTH_DARK)
  }

  // ---- extras ----------------------------------------------------------------------------
  if (t.cigar) {
    p.row(17, 14, 16, '#5a3a22')
    p.px(15, 17, '#6f4a2c')
    p.px(17, 17, EMBER)
  }
  if (t.spectacles || t.monocle) {
    const rim = rnd() < 0.5 ? GOLD : '#2a2118'
    const ring = (x0: number, x1: number) => {
      p.row(11, x0, x1, rim)
      p.row(14, x0, x1, rim)
      p.rect(x0, 12, x0, 13, rim)
      p.rect(x1, 12, x1, 13, rim)
    }
    if (t.spectacles) {
      ring(6, 10)
      ring(13, 17)
      p.px(11, 12, rim)
      p.px(12, 12, rim)
      p.px(7, 12, mix(EYE_WHITE, '#ffffff', 0.5)) // lens glint
      p.px(14, 12, mix(EYE_WHITE, '#ffffff', 0.5))
    } else {
      ring(13, 17)
      p.px(17, 15, rim)
      p.px(18, 16, rim)
    }
  }
  if (t.earrings) {
    p.px(4, 14, t.pearls ? PEARL : GOLD)
    p.px(19, 14, t.pearls ? PEARL : GOLD)
  }
}

/** Things that sit in front of hair and hats: the nervous sweat drop and cigar smoke. */
function paintExtras(p: Painter, t: PortraitTraits, emotion: PortraitEmotion): void {
  if (emotion === 'nervous') {
    p.px(18, 9, SWEAT_LIGHT)
    p.px(18, 10, SWEAT)
    p.px(19, 10, SWEAT_LIGHT)
    p.px(18, 11, SWEAT)
  }
  if (t.cigar && emotion !== 'angry') {
    p.px(18, 15, SMOKE)
    p.px(19, 14, mix(SMOKE, '#ffffff', 0.4))
    p.px(18, 13, mix(SMOKE, '#ffffff', 0.6))
  }
}

function paintPearls(p: Painter): void {
  const pts: Array<[number, number]> = [
    [8, 22],
    [9, 23],
    [10, 23],
    [11, 23],
    [12, 23],
    [13, 23],
    [14, 23],
    [15, 22],
  ]
  pts.forEach(([x, y], i) => p.px(x, y, i % 2 === 0 ? PEARL : PEARL_SHADE))
  p.px(11, 24, PEARL_SHADE)
  p.px(12, 24, PEARL)
}

function paintDisc(p: Painter, emotion: PortraitEmotion): void {
  const tint = EMOTION_TINT[emotion]
  const outer = mix(tint, '#15100c', 0.62)
  const inner = mix(tint, '#15100c', 0.42)
  const cx = 11.5
  const cy = 13
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      const d = Math.hypot(x - cx, y - cy)
      if (d <= 11.6) p.px(x, y, d <= 8.4 ? inner : outer, false)
    }
  }
}

function paintOutline(p: Painter): void {
  const toOutline: number[] = []
  for (let y = 0; y < GRID_H; y++) {
    for (let x = 0; x < GRID_W; x++) {
      if (p.isFigure(x, y)) continue
      if (p.isFigure(x - 1, y) || p.isFigure(x + 1, y) || p.isFigure(x, y - 1) || p.isFigure(x, y + 1)) toOutline.push(y * GRID_W + x)
    }
  }
  for (const i of toOutline) p.cells[i] = OUTLINE
}

/** Build the 24×28 grid for a suspect. Deterministic for the same {traits, emotion, seed, blink}. */
export function buildPortrait(opts: BuildOptions): PortraitGrid {
  const { traits: t, seed } = opts
  const emotion = opts.emotion ?? 'neutral'
  const rnd = mulberry32(hashString(seed))
  const p = new Painter()

  // seed-driven choices (independent of emotion so the face is stable across expressions)
  const jawRoll = rnd()
  const jaw: 'round' | 'square' | 'narrow' = jawRoll < 0.34 ? 'round' : jawRoll < 0.67 ? 'square' : 'narrow'
  const traits: PortraitTraits = { ...t }
  if (!t.hairColorExplicit) {
    const roll = rnd()
    if (t.age === 'old') traits.hairColor = roll < 0.5 ? 'grey' : 'white'
    else if (t.greyTemples) traits.hairColor = roll < 0.6 ? 'brown' : 'black'
    else traits.hairColor = roll < 0.5 ? 'brown' : roll < 0.85 ? 'black' : roll < 0.95 ? 'blonde' : 'red'
  }
  if (!t.hairStyleExplicit) {
    if (t.headwear === 'cap') traits.hairStyle = 'bun' // hair pinned up under a maid's cap
    else if (t.presentation === 'unknown') traits.hairStyle = rnd() < 0.5 ? 'short' : 'bob'
  }
  const rows = headRows(jaw)

  if (opts.disc !== false) paintDisc(p, emotion)
  paintTorso(p, traits, SKIN[traits.skin], rnd)
  if (traits.pearls) paintPearls(p)
  paintHead(p, traits, emotion, rows)
  paintHair(p, traits, rows, rnd)
  paintHeadwear(p, traits, rnd)
  paintFeatures(p, traits, emotion, !!opts.blink, rows, rnd)
  paintExtras(p, traits, emotion)
  paintOutline(p)

  return { w: GRID_W, h: GRID_H, cells: p.cells }
}

/** Convenience: parse + build in one go. */
export function portraitFor(prompt: string | null | undefined, seed: string, emotion: PortraitEmotion = 'neutral', blink = false): PortraitGrid {
  return buildPortrait({ traits: parseTraits(prompt), emotion, seed, blink })
}

// ---------------------------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------------------------

/**
 * Paint the grid into a canvas at an integer scale. Returns false when a 2D context is unavailable
 * (e.g. jsdom) so callers can fall back to SVG.
 */
export function renderToCanvas(canvas: HTMLCanvasElement, grid: PortraitGrid, scale = 4): boolean {
  const ctx = canvas.getContext('2d')
  if (!ctx) return false
  const w = grid.w * scale
  const h = grid.h * scale
  if (canvas.width !== w) canvas.width = w
  if (canvas.height !== h) canvas.height = h
  ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, w, h)
  for (let y = 0; y < grid.h; y++) {
    for (let x = 0; x < grid.w; x++) {
      const c = grid.cells[y * grid.w + x]
      if (!c) continue
      ctx.fillStyle = c
      ctx.fillRect(x * scale, y * scale, scale, scale)
    }
  }
  return true
}

export interface GridRun {
  x: number
  y: number
  w: number
  color: string
}

/** Horizontal runs of identical colour — what an SVG renderer draws as <rect>s. */
export function gridRuns(grid: PortraitGrid): GridRun[] {
  const runs: GridRun[] = []
  for (let y = 0; y < grid.h; y++) {
    let x = 0
    while (x < grid.w) {
      const c = grid.cells[y * grid.w + x]
      if (!c) {
        x++
        continue
      }
      let run = 1
      while (x + run < grid.w && grid.cells[y * grid.w + x + run] === c) run++
      runs.push({ x, y, w: run, color: c })
      x += run
    }
  }
  return runs
}

/** SVG markup for the grid (run-length merged per row). `shapeRendering="crispEdges"` keeps pixels sharp. */
export function gridToSvg(grid: PortraitGrid, opts: { title?: string; className?: string; size?: number } = {}): string {
  const rects = gridRuns(grid).map((r) => `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="1" fill="${r.color}"/>`)
  const size = opts.size ?? 96
  const height = Math.round((size * grid.h) / grid.w)
  const title = opts.title ? `<title>${escapeXml(opts.title)}</title>` : ''
  const cls = opts.className ? ` class="${escapeXml(opts.className)}"` : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${grid.w} ${grid.h}" width="${size}" height="${height}" shape-rendering="crispEdges" role="img"${cls}>${title}${rects.join('')}</svg>`
}

function escapeXml(s: string): string {
  return s.replace(/[<>&"']/g, (ch) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' })[ch] ?? ch)
}

/** Alt text per DESIGN §8. */
export function portraitAlt(name: string, emotion: PortraitEmotion): string {
  return `Portrait of ${name}, looking ${emotion}`
}

/** Emotion tint colour (CSS variable fallbacks for callers without the stylesheet). */
export function emotionColor(emotion: PortraitEmotion): string {
  return EMOTION_TINT[emotion]
}

/** Map any emotion string coming from the API onto a portrait variant (unknown → neutral). */
export function toPortraitEmotion(e: string | null | undefined): PortraitEmotion {
  return (PORTRAIT_EMOTIONS as readonly string[]).includes(e ?? '') ? (e as PortraitEmotion) : 'neutral'
}
