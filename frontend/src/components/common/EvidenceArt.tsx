/**
 * Painted evidence plate when `/evidence/{pack}/{id}.webp` exists; else EvidenceIcon.
 */
import { useState } from 'react'
import { EvidenceIcon } from '@/components/common/EvidenceIcon'
import { evidenceArtUrl } from '@/lib/briefingStory'
import { cn } from '@/lib/cn'

export interface EvidenceArtProps {
  caseId: string
  evidenceId: string
  name: string
  description?: string
  size?: number
  className?: string
  iconColor?: string
  /** cover = cropped thumb; contain = full object (briefing plates). */
  fit?: 'cover' | 'contain'
}

export function EvidenceArt({
  caseId,
  evidenceId,
  name,
  description,
  size = 40,
  className,
  iconColor = 'currentColor',
  fit = 'cover',
}: EvidenceArtProps) {
  const [imgOk, setImgOk] = useState(true)
  const src = evidenceArtUrl(caseId, evidenceId)

  if (imgOk) {
    return (
      <img
        className={cn('evidence-art', className)}
        src={src}
        alt=""
        width={size}
        height={size}
        style={{
          width: size,
          height: size,
          objectFit: fit,
          objectPosition: 'center',
          background: fit === 'contain' ? '#0a0503' : undefined,
          borderRadius: 4,
          flex: '0 0 auto',
        }}
        onError={() => setImgOk(false)}
        draggable={false}
      />
    )
  }

  return (
    <span
      className={cn('evidence-art evidence-art--fallback', className)}
      style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flex: '0 0 auto',
      }}
      aria-hidden="true"
    >
      <EvidenceIcon name={name} description={description} size={Math.round(size * 0.55)} color={iconColor} />
    </span>
  )
}

export default EvidenceArt
