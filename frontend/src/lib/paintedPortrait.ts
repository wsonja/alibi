/**
 * Painted portrait URLs for hand-authored / concept-board art under
 * `frontend/public/portraits/{pack}/` (docs/IMMERSIVE_REDESIGN.md, docs/art-direction/vane_hall/).
 *
 * Packs ship `neutral` first; emotion variants are optional. Missing emotion → neutral.
 * Unknown pack / suspect → null (caller falls back to PixelPortrait).
 */
import { toPortraitEmotion, type PortraitEmotion } from '@/lib/pixelPortrait'

/** Case ids → public folder under /portraits/ */
const CASE_PACK: Record<string, string> = {
  vane_hall_1923: 'vane_hall',
  vane_hall: 'vane_hall',
}

/** Suspects that have at least a `_neutral.webp` in the pack. */
const PACK_CAST: Record<string, ReadonlySet<string>> = {
  vane_hall: new Set(['margaret', 'crane', 'pell', 'ada']),
}

export function portraitPackForCase(caseId: string | null | undefined): string | null {
  if (!caseId) return null
  if (CASE_PACK[caseId]) return CASE_PACK[caseId]!
  if (caseId.startsWith('vane_hall')) return 'vane_hall'
  return null
}

export function packHasSuspect(pack: string, suspectId: string): boolean {
  return PACK_CAST[pack]?.has(suspectId) ?? false
}

/** Bust portrait (≥ ~72px). Prefer emotion file, then neutral. */
export function paintedBustUrl(pack: string, suspectId: string, emotion?: string | null): string {
  const emo = toPortraitEmotion(emotion)
  return `/portraits/${pack}/${suspectId}_${emo}.webp`
}

export function paintedNeutralUrl(pack: string, suspectId: string): string {
  return `/portraits/${pack}/${suspectId}_neutral.webp`
}

/** Square crop for list chips. */
export function paintedAvatarUrl(pack: string, suspectId: string): string {
  return `/portraits/${pack}/${suspectId}_avatar.webp`
}

export function preferAvatar(size: number): boolean {
  return size <= 64
}

export function resolvePaintedSrc(opts: {
  caseId?: string | null
  suspectId: string
  emotion?: string | null
  size: number
}): { pack: string; src: string; fallbackSrc: string } | null {
  const pack = portraitPackForCase(opts.caseId) ?? (packHasSuspect('vane_hall', opts.suspectId) ? 'vane_hall' : null)
  if (!pack || !packHasSuspect(pack, opts.suspectId)) return null
  if (preferAvatar(opts.size)) {
    return {
      pack,
      src: paintedAvatarUrl(pack, opts.suspectId),
      fallbackSrc: paintedNeutralUrl(pack, opts.suspectId),
    }
  }
  const emo = toPortraitEmotion(opts.emotion)
  const primary = paintedBustUrl(pack, opts.suspectId, emo)
  const neutral = paintedNeutralUrl(pack, opts.suspectId)
  return {
    pack,
    src: primary,
    fallbackSrc: emo === 'neutral' ? primary : neutral,
  }
}

export type { PortraitEmotion }
