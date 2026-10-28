/**
 * Face / voice sensors (PLAN §11). FaceLandmarker runs in the browser; nothing is uploaded.
 * Emits a FaceSample about every 2s while the video is playing.
 * GPU WebGL often fails (kGpuService); createBrowserFaceLandmarker falls back to CPU.
 */
import { type FaceLandmarker, type FaceLandmarkerResult } from '@mediapipe/tasks-vision'
import type { FaceSample, VoiceSample } from '@/store/sensors'
import type { Composure, Gaze } from '@/api/types'
import { createBrowserFaceLandmarker } from '@/sensors/faceLandmarker'

const SAMPLE_MS = 2000

let landmarker: FaceLandmarker | null = null
let raf = 0
let running = false
let lastSampleAt = 0
let lastVideoTime = -1
let blinkEvents: number[] = []

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n))
}

function blend(result: FaceLandmarkerResult, name: string): number {
  const cats = result.faceBlendshapes?.[0]?.categories
  if (!cats) return 0
  const hit = cats.find((c) => c.categoryName === name)
  return hit?.score ?? 0
}

function yawFromMatrix(result: FaceLandmarkerResult): number {
  const m = result.facialTransformationMatrixes?.[0]?.data
  if (!m || m.length < 11) return 0
  // column-major 4×4; approximate yaw from m00/m02
  return Math.atan2(m[8]!, m[0]!)
}

function toSample(result: FaceLandmarkerResult, now: number): FaceSample {
  const blinkL = blend(result, 'eyeBlinkLeft')
  const blinkR = blend(result, 'eyeBlinkRight')
  const blink = (blinkL + blinkR) / 2
  if (blink > 0.5) blinkEvents.push(now)
  blinkEvents = blinkEvents.filter((t) => now - t < 60_000)
  const blinkRate = blinkEvents.length // per minute window

  const brow = (blend(result, 'browDownLeft') + blend(result, 'browDownRight')) / 2
  const lookOutL = blend(result, 'eyeLookOutLeft')
  const lookOutR = blend(result, 'eyeLookOutRight')
  const yaw = yawFromMatrix(result)
  const yawNorm = clamp(yaw / 0.6, -1, 1)
  const gazeX = clamp(lookOutR - lookOutL + 0.5 * yawNorm, -1, 1)

  const normBlink = clamp((blinkRate - 10) / 30, 0, 1)
  const score = clamp(1 - 0.5 * normBlink - 0.3 * brow - 0.2 * Math.abs(gazeX), 0, 1)
  const composure: Composure = score < 0.4 ? 'nervous' : score < 0.7 ? 'neutral' : 'confident'
  const gaze: Gaze = gazeX < -0.3 ? 'away' : gazeX > 0.3 ? 'notebook' : 'suspect'

  return {
    composure,
    gaze,
    score,
    blinkRate,
    brow,
    gazeX,
    faceDetected: (result.faceLandmarks?.length ?? 0) > 0,
  }
}

async function ensureLandmarker(): Promise<FaceLandmarker> {
  if (landmarker) return landmarker
  const created = await createBrowserFaceLandmarker()
  landmarker = created.landmarker
  return landmarker
}

/** Start the face pipeline on a playing <video>. */
export async function startFace(video: HTMLVideoElement, onSample: (s: FaceSample) => void): Promise<void> {
  stopFace()
  running = true
  const lm = await ensureLandmarker()
  if (!running) return

  const tick = () => {
    if (!running) return
    raf = requestAnimationFrame(tick)
    if (video.readyState < 2) return
    const t = video.currentTime
    if (t === lastVideoTime) return
    lastVideoTime = t
    let result: FaceLandmarkerResult
    try {
      result = lm.detectForVideo(video, performance.now())
    } catch {
      return
    }
    const now = Date.now()
    if (now - lastSampleAt < SAMPLE_MS) return
    lastSampleAt = now
    if ((result.faceLandmarks?.length ?? 0) === 0) {
      onSample({ composure: 'neutral', gaze: 'away', score: 0.5, faceDetected: false })
      return
    }
    onSample(toSample(result, now))
  }
  raf = requestAnimationFrame(tick)
}

export function stopFace(): void {
  running = false
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  lastVideoTime = -1
  lastSampleAt = 0
  blinkEvents = []
}

export function faceRunning(): boolean {
  return running
}

/** Start voice-stress sampling on a mic stream. Returns a stop function. */
export function startVoiceStress(stream: MediaStream, onSample: (s: VoiceSample) => void): () => void {
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  if (!Ctx) return () => {}
  const ctx = new Ctx()
  const src = ctx.createMediaStreamSource(stream)
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 2048
  src.connect(analyser)
  const data = new Uint8Array(analyser.fftSize)
  let alive = true
  const id = window.setInterval(() => {
    if (!alive) return
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) {
      const v = (data[i]! - 128) / 128
      sum += v * v
    }
    const rms = Math.sqrt(sum / data.length)
    onSample({ stress: clamp(rms * 4, 0, 1) })
  }, 500)
  return () => {
    alive = false
    clearInterval(id)
    try {
      src.disconnect()
      void ctx.close()
    } catch {
      /* ignore */
    }
  }
}
