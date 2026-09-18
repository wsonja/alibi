/**
 * AvatarCapture — modal that turns a webcam frame (or an uploaded picture) into the player's pixel avatar.
 *
 * Everything stays in the browser: the frame is drawn to an offscreen canvas, cropped to the oval guide, reduced
 * to AVATAR_W×AVATAR_H palette colours (lib/avatar.ts) and only that grid is kept (store/avatar.ts). The camera
 * stream is stopped the moment the dialog closes.
 *
 *   <AvatarCapture open={open} onClose={() => setOpen(false)} />
 */
import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import { Button } from '@/components/common/Button'
import { Modal } from '@/components/common/Modal'
import { AVATAR_H, AVATAR_W, avatarFromPixels, cropRect } from '@/lib/avatar'
import type { PortraitGrid } from '@/lib/pixelPortrait'
import { useAvatar } from '@/store/avatar'
import { PlayerAvatar } from './PlayerAvatar'

export interface AvatarCaptureProps {
  open: boolean
  onClose: () => void
  /** called after the avatar has been saved (before onClose) */
  onSaved?: (grid: PortraitGrid) => void
}

type Status = 'starting' | 'live' | 'snapped' | 'error'

/** Source pixels per avatar cell when sampling the crop. */
const SAMPLE_SCALE = 4
const SAMPLE_W = AVATAR_W * SAMPLE_SCALE
const SAMPLE_H = AVATAR_H * SAMPLE_SCALE
/** Viewfinder canvas resolution (CSS scales it to fit). */
const VIEW_W = 240
const VIEW_H = 280
/** How often the live pixel preview is recomputed. */
const PREVIEW_MS = 120

export const PRIVACY_LINE = 'Your picture becomes a few hundred pixels right here in your browser. The photo itself is never saved or sent anywhere.'

function cameraError(e: unknown): string {
  if (e instanceof DOMException) {
    if (e.name === 'NotAllowedError' || e.name === 'SecurityError') return 'Camera permission was refused. You can upload a picture instead.'
    if (e.name === 'NotFoundError' || e.name === 'OverconstrainedError') return 'No camera was found. You can upload a picture instead.'
    if (e.name === 'NotReadableError') return 'The camera is busy in another app. You can upload a picture instead.'
  }
  return 'Could not start the camera. You can upload a picture instead.'
}

export function AvatarCapture({ open, onClose, onSaved }: AvatarCaptureProps) {
  const setAvatar = useAvatar((s) => s.setGrid)
  const [status, setStatus] = useState<Status>('starting')
  const [error, setError] = useState<string | null>(null)
  const [grid, setGrid] = useState<PortraitGrid | null>(null)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const viewRef = useRef<HTMLCanvasElement | null>(null)
  const sampleRef = useRef<HTMLCanvasElement | null>(null)
  const fileRef = useRef<HTMLInputElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const rafRef = useRef(0)
  const lastPreviewRef = useRef(0)
  const statusRef = useRef<Status>('starting')
  /** bumps on every start (and on close) so a stream that resolves late is discarded */
  const sessionRef = useRef(0)

  const update = useCallback((s: Status) => {
    statusRef.current = s
    setStatus(s)
  }, [])

  /** Draw `source` cropped to the 6:7 box into the viewfinder and, when `sample`, reduce it to a grid. */
  const process = useCallback((source: CanvasImageSource, width: number, height: number, mirror: boolean, sample: boolean): PortraitGrid | null => {
    const view = viewRef.current
    if (!view) return null
    const { sx, sy, sw, sh } = cropRect(width, height)
    const draw = (canvas: HTMLCanvasElement, w: number, h: number, readBack: boolean): CanvasRenderingContext2D | null => {
      const ctx = readBack ? canvas.getContext('2d', { willReadFrequently: true }) : canvas.getContext('2d')
      if (!ctx) return null
      if (canvas.width !== w) canvas.width = w
      if (canvas.height !== h) canvas.height = h
      ctx.save()
      if (mirror) {
        ctx.translate(w, 0)
        ctx.scale(-1, 1)
      }
      ctx.drawImage(source, sx, sy, sw, sh, 0, 0, w, h)
      ctx.restore()
      return ctx
    }
    draw(view, VIEW_W, VIEW_H, false)
    if (!sample) return null
    const canvas = sampleRef.current ?? (sampleRef.current = document.createElement('canvas'))
    const ctx = draw(canvas, SAMPLE_W, SAMPLE_H, true)
    if (!ctx) return null
    return avatarFromPixels(ctx.getImageData(0, 0, SAMPLE_W, SAMPLE_H))
  }, [])

  const loop = useCallback(
    function tick(now: number) {
      rafRef.current = requestAnimationFrame(tick)
      if (statusRef.current !== 'live') return
      const video = videoRef.current
      if (!video || video.readyState < 2 || !video.videoWidth) return
      const sample = now - lastPreviewRef.current >= PREVIEW_MS
      const g = process(video, video.videoWidth, video.videoHeight, true, sample)
      if (sample) {
        lastPreviewRef.current = now
        if (g) setGrid(g)
      }
    },
    [process],
  )

  const stopCamera = useCallback(() => {
    cancelAnimationFrame(rafRef.current)
    for (const track of streamRef.current?.getTracks() ?? []) {
      try {
        track.stop()
      } catch {
        /* ignore */
      }
    }
    streamRef.current = null
    const video = videoRef.current
    if (video) {
      try {
        video.pause()
        video.srcObject = null
      } catch {
        /* ignore */
      }
    }
  }, [])

  const startCamera = useCallback(async () => {
    const session = ++sessionRef.current
    setError(null)
    setGrid(null)
    update('starting')
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setError('This browser cannot open a camera. You can upload a picture instead.')
      update('error')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false })
      const video = videoRef.current
      if (session !== sessionRef.current || !video) {
        for (const track of stream.getTracks()) track.stop()
        return
      }
      streamRef.current = stream
      video.srcObject = stream
      try {
        await video.play()
      } catch {
        /* autoplay may be deferred; frames arrive once it starts */
      }
      if (session !== sessionRef.current) return
      lastPreviewRef.current = 0
      update('live')
      cancelAnimationFrame(rafRef.current)
      rafRef.current = requestAnimationFrame(loop)
    } catch (e) {
      if (session !== sessionRef.current) return
      setError(cameraError(e))
      update('error')
    }
  }, [loop, update])

  useEffect(() => {
    if (!open) return
    void startCamera()
    return () => {
      sessionRef.current += 1
      stopCamera()
    }
  }, [open, startCamera, stopCamera])

  const snap = () => {
    const video = videoRef.current
    if (statusRef.current !== 'live' || !video) return
    const g = process(video, video.videoWidth, video.videoHeight, true, true)
    if (g) setGrid(g)
    update('snapped')
  }

  const retake = () => {
    if (streamRef.current) {
      lastPreviewRef.current = 0
      update('live')
    } else {
      void startCamera()
    }
  }

  const use = () => {
    if (!grid) return
    setAvatar(grid)
    onSaved?.(grid)
    onClose()
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const bitmap = await createImageBitmap(file)
      try {
        const g = process(bitmap, bitmap.width, bitmap.height, false, true)
        if (!g) throw new Error('no canvas')
        setGrid(g)
        setError(null)
        update('snapped')
      } finally {
        bitmap.close()
      }
    } catch {
      setError('That picture could not be read. Try a JPEG or PNG.')
    }
  }

  const live = status === 'live'
  const snapped = status === 'snapped'

  return (
    <Modal open={open} onClose={onClose} title="Your detective — take a photo" width={640}>
      <p className="ink-soft" style={{ margin: '0 0 12px', fontSize: 14 }}>
        {PRIVACY_LINE}
      </p>

      <div className="flex flex-wrap items-center justify-center gap-5">
        <div className="viewfinder" aria-busy={status === 'starting'}>
          <video ref={videoRef} muted playsInline autoPlay aria-hidden="true" style={{ position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none' }} />
          <canvas ref={viewRef} width={VIEW_W} height={VIEW_H} role="img" aria-label={snapped ? 'Your photo' : 'Camera preview'} />
          {live || snapped ? <div className="viewfinder__guide" aria-hidden="true" /> : null}
          {status === 'starting' ? <div className="viewfinder__msg mono">Starting the camera…</div> : null}
          {status === 'error' ? <div className="viewfinder__msg">{error}</div> : null}
        </div>
        <span aria-hidden="true" className="display display--gold" style={{ fontSize: 22 }}>
          →
        </span>
        <div className="flex flex-col items-center gap-2">
          <div className="avatar-frame">
            <PlayerAvatar grid={grid} size={144} title={snapped ? 'Your avatar' : 'Live preview'} />
          </div>
          <span className="label-caps" style={{ fontSize: 10 }}>
            {snapped ? 'Your avatar' : live ? 'Live preview' : 'Preview'}
          </span>
        </div>
      </div>

      {error && status !== 'error' ? (
        <p role="alert" style={{ color: 'var(--red-600)', fontSize: 14, margin: '10px 0 0', textAlign: 'center' }}>
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-3 justify-center mt-4">
        {live ? (
          <Button onClick={snap} disabled={!grid}>
            📷 Snap
          </Button>
        ) : null}
        {snapped ? (
          <>
            <Button onClick={use}>✓ Use this</Button>
            <Button variant="black" onClick={retake}>
              ↻ Retake
            </Button>
          </>
        ) : null}
        {status === 'error' ? (
          <Button variant="black" onClick={() => void startCamera()}>
            Try the camera again
          </Button>
        ) : null}
        <Button variant="ghost" onClick={() => fileRef.current?.click()}>
          Upload a picture instead
        </Button>
        <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => void onFile(e)} aria-label="Upload a picture" tabIndex={-1} />
      </div>

      <p className="ink-soft text-center" style={{ margin: '10px 0 0', fontSize: 13 }}>
        Put your face inside the oval. Light in front of you works best.
      </p>
    </Modal>
  )
}

export default AvatarCapture
