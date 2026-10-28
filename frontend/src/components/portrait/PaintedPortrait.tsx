/**
 * PaintedPortrait — concept-board / commissioned faces from `/portraits/{pack}/`.
 * Falls back to PixelPortrait when no pack file exists or the image fails to load.
 */
import { useEffect, useState } from 'react'
import { cn } from '@/lib/cn'
import { portraitAlt, toPortraitEmotion } from '@/lib/pixelPortrait'
import { resolvePaintedSrc } from '@/lib/paintedPortrait'
import { PixelPortrait, type PixelPortraitProps } from '@/components/portrait/PixelPortrait'

export type PaintedPortraitProps = PixelPortraitProps & {
  /** Game case id (e.g. vane_hall_1923). Defaults to vane_hall pack when the suspect id matches. */
  caseId?: string | null
}

export function PaintedPortrait({
  suspect,
  emotion,
  size = 96,
  className,
  dim,
  title,
  caseId,
  ...pixelRest
}: PaintedPortraitProps) {
  const emo = toPortraitEmotion(emotion)
  const resolved = resolvePaintedSrc({ caseId, suspectId: suspect.id, emotion: emo, size })
  const [src, setSrc] = useState<string | null>(resolved?.src ?? null)
  const [stage, setStage] = useState<'primary' | 'fallback' | 'pixel'>(resolved ? 'primary' : 'pixel')

  useEffect(() => {
    const next = resolvePaintedSrc({ caseId, suspectId: suspect.id, emotion: emo, size })
    if (!next) {
      setSrc(null)
      setStage('pixel')
      return
    }
    setSrc(next.src)
    setStage('primary')
  }, [caseId, suspect.id, emo, size])

  if (stage === 'pixel' || !src || !resolved) {
    return (
      <PixelPortrait
        suspect={suspect}
        emotion={emotion}
        size={size}
        className={className}
        dim={dim}
        title={title}
        {...pixelRest}
      />
    )
  }

  const alt = title ?? portraitAlt(suspect.name, emo)
  const px = typeof size === 'number' ? size : 96

  return (
    <span
      className={cn('painted-portrait', dim && 'painted-portrait--dim', className)}
      style={{
        display: 'inline-flex',
        width: px,
        height: px,
        borderRadius: '50%',
        overflow: 'hidden',
        boxShadow: '0 0 0 2px rgba(201,162,75,.55), 0 4px 14px rgba(0,0,0,.45)',
        background: '#1a100c',
        flexShrink: 0,
        opacity: dim ? 0.55 : 1,
        transition: 'opacity .2s ease',
      }}
      role="img"
      aria-label={alt}
    >
      <img
        src={src}
        alt=""
        width={px}
        height={px}
        draggable={false}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: 'center 18%',
          display: 'block',
        }}
        onError={() => {
          if (stage === 'primary' && resolved.fallbackSrc !== src) {
            setSrc(resolved.fallbackSrc)
            setStage('fallback')
            return
          }
          setStage('pixel')
          setSrc(null)
        }}
      />
    </span>
  )
}

export default PaintedPortrait
