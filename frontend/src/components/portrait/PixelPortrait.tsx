/**
 * PixelPortrait — procedural pixel-art face for a suspect (docs/DESIGN.md §6, INTERFACES §7).
 *
 *   <PixelPortrait suspect={s} emotion={s.emotion} size={96} />
 *
 * Renders into a <canvas> (image-rendering: pixelated). When no 2D context is available (jsdom, some privacy
 * browsers) it falls back to inline SVG rects. Blinks every few seconds unless low-sensory / reduced-motion.
 * Alt text: "Portrait of <name>, looking <emotion>".
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { cn } from '@/lib/cn'
import { prefersReducedMotion } from '@/lib/motion'
import { GRID_H, GRID_W, buildPortrait, gridRuns, parseTraits, portraitAlt, renderToCanvas, toPortraitEmotion, type PortraitEmotion } from '@/lib/pixelPortrait'
import { useUI } from '@/store/ui'

export type PortraitSize = 48 | 56 | 96 | 160 | 200 | number

export interface PixelPortraitProps {
  suspect: { id: string; name: string; portrait_prompt?: string | null }
  emotion?: PortraitEmotion | string | null
  size?: PortraitSize
  className?: string
  /** dims the portrait (reply pending) */
  dim?: boolean
  /** force the eyes shut (tests / stills) */
  blink?: boolean
  /** disable the idle blink animation */
  still?: boolean
  /** draw without the emotion-tinted disc */
  noDisc?: boolean
  title?: string
}

const CANVAS_SCALE = 4

export function PixelPortrait({ suspect, emotion, size = 96, className, dim, blink, still, noDisc, title }: PixelPortraitProps) {
  const lowSensory = useUI((s) => s.a11y.lowSensory)
  const emo = toPortraitEmotion(emotion)
  const traits = useMemo(() => parseTraits(suspect.portrait_prompt), [suspect.portrait_prompt])
  const [autoBlink, setAutoBlink] = useState(false)
  const [fallback, setFallback] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const blinkEnabled = !still && blink === undefined && !lowSensory && !prefersReducedMotion()
  const blinking = blink ?? (blinkEnabled && autoBlink)
  const grid = useMemo(() => buildPortrait({ traits, emotion: emo, seed: suspect.id, blink: blinking, disc: !noDisc }), [traits, emo, suspect.id, blinking, noDisc])

  // idle blink
  useEffect(() => {
    if (!blinkEnabled) return
    let open: ReturnType<typeof setTimeout> | null = null
    let close: ReturnType<typeof setTimeout> | null = null
    let cancelled = false
    const schedule = () => {
      if (cancelled) return
      const wait = 2600 + Math.random() * 3800
      close = setTimeout(() => {
        if (cancelled) return
        setAutoBlink(true)
        open = setTimeout(() => {
          if (cancelled) return
          setAutoBlink(false)
          schedule()
        }, 130)
      }, wait)
    }
    schedule()
    return () => {
      cancelled = true
      if (open) clearTimeout(open)
      if (close) clearTimeout(close)
    }
  }, [blinkEnabled, suspect.id])

  // paint
  useEffect(() => {
    if (fallback) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ok = renderToCanvas(canvas, grid, CANVAS_SCALE)
    if (!ok) setFallback(true)
  }, [grid, fallback])

  const height = Math.round((size * GRID_H) / GRID_W)
  const alt = title ?? portraitAlt(suspect.name, emo)
  const cls = cn('pixel-portrait', dim && 'pixel-portrait--dim', className)

  if (fallback) {
    return (
      <svg
        className={cls}
        role="img"
        aria-label={alt}
        viewBox={`0 0 ${GRID_W} ${GRID_H}`}
        width={size}
        height={height}
        shapeRendering="crispEdges"
        data-suspect={suspect.id}
        data-emotion={emo}
      >
        <title>{alt}</title>
        {gridRuns(grid).map((r) => (
          <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width={r.w} height={1} fill={r.color} />
        ))}
      </svg>
    )
  }

  return (
    <canvas
      ref={canvasRef}
      className={cls}
      role="img"
      aria-label={alt}
      width={GRID_W * CANVAS_SCALE}
      height={GRID_H * CANVAS_SCALE}
      style={{ width: size, height }}
      data-suspect={suspect.id}
      data-emotion={emo}
    />
  )
}

export default PixelPortrait
