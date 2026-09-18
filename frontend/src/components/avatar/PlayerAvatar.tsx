/**
 * PlayerAvatar — the player's pixel avatar (store/avatar.ts) drawn with the suspects' renderer, or a detective
 * silhouette while no photo has been taken. Same rounded `.pixel-portrait` frame as the cast.
 *
 *   <PlayerAvatar size={96} />                        the stored avatar (or the silhouette)
 *   <PlayerAvatar grid={preview} size={144} />        a specific grid (the capture modal's live preview)
 *   <PlayerAvatar size={20} silhouette={false} />     nothing at all until a photo exists (inline "You" labels)
 */
import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/cn'
import { gridRuns, renderToCanvas, type PortraitGrid } from '@/lib/pixelPortrait'
import { useAvatar } from '@/store/avatar'

export interface PlayerAvatarProps {
  size?: number
  className?: string
  /** draw this grid instead of the stored one (null forces the silhouette) */
  grid?: PortraitGrid | null
  /** show the silhouette when there is no avatar (default true; false renders nothing) */
  silhouette?: boolean
  dim?: boolean
  title?: string
}

const CANVAS_SCALE = 4

export function PlayerAvatar({ size = 96, className, grid: gridProp, silhouette = true, dim, title = 'Your detective' }: PlayerAvatarProps) {
  const stored = useAvatar((s) => s.grid)
  const grid = gridProp === undefined ? stored : gridProp
  const cls = cn(dim && 'pixel-portrait--dim', className)
  if (!grid) return silhouette ? <DetectiveSilhouette size={size} className={cls} title={`${title} (no photo yet)`} /> : null
  return <AvatarCanvas grid={grid} size={size} className={cls} title={title} />
}

function AvatarCanvas({ grid, size, className, title }: { grid: PortraitGrid; size: number; className?: string; title: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [fallback, setFallback] = useState(false)

  useEffect(() => {
    if (fallback) return
    const canvas = canvasRef.current
    if (!canvas) return
    if (!renderToCanvas(canvas, grid, CANVAS_SCALE)) setFallback(true)
  }, [grid, fallback])

  const height = Math.round((size * grid.h) / grid.w)
  const cls = cn('pixel-portrait', className)

  if (fallback) {
    return (
      <svg className={cls} role="img" aria-label={title} viewBox={`0 0 ${grid.w} ${grid.h}`} width={size} height={height} shapeRendering="crispEdges" data-avatar="grid">
        <title>{title}</title>
        {gridRuns(grid).map((r) => (
          <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width={r.w} height={1} fill={r.color} />
        ))}
      </svg>
    )
  }

  return <canvas ref={canvasRef} className={cls} role="img" aria-label={title} width={grid.w * CANVAS_SCALE} height={grid.h * CANVAS_SCALE} style={{ width: size, height }} data-avatar="grid" />
}

/** Fedora-and-collar silhouette on a dark disc, 6:7 like the portraits. */
export function DetectiveSilhouette({ size = 96, className, title = 'Your detective (no photo yet)' }: { size?: number; className?: string; title?: string }) {
  const height = Math.round((size * 7) / 6)
  return (
    <svg className={cn('pixel-portrait', className)} role="img" aria-label={title} viewBox="0 0 24 28" width={size} height={height} shapeRendering="crispEdges" data-avatar="silhouette">
      <title>{title}</title>
      <rect width="24" height="28" fill="#2a1d15" />
      {/* hat */}
      <rect x="5" y="7" width="14" height="2" fill="#15100c" />
      <rect x="7" y="3" width="10" height="4" fill="#15100c" />
      <rect x="7" y="6" width="10" height="1" fill="#7e1414" />
      {/* face in shadow */}
      <rect x="8" y="9" width="8" height="7" fill="#3b2116" />
      <rect x="9" y="11" width="2" height="1" fill="#f0d48a" opacity="0.8" />
      <rect x="13" y="11" width="2" height="1" fill="#f0d48a" opacity="0.8" />
      {/* collar and coat */}
      <rect x="10" y="16" width="4" height="2" fill="#3b2116" />
      <rect x="4" y="18" width="16" height="10" fill="#5a331c" />
      <rect x="10" y="18" width="4" height="10" fill="#3b2116" />
      <rect x="6" y="18" width="4" height="3" fill="#4a2a16" />
      <rect x="14" y="18" width="4" height="3" fill="#4a2a16" />
    </svg>
  )
}

export default PlayerAvatar
