/**
 * Sensors store (docs/INTERFACES.md §7, PLAN §11): camera consent, composure, gaze, voice stress.
 * `start()` / `stop()` delegate to src/sensors/index.ts (stubs in the foundation; the sensors lane fills them in).
 * `signal()` returns the `player_signal` to attach to every turn/confront call, or undefined when sensors are off.
 * Nothing here ever leaves the browser except the three small fields in `signal()`.
 */
import { create } from 'zustand'
import type { Composure, Gaze, PlayerSignal } from '@/api/types'
import { startFace, startVoiceStress, stopFace } from '@/sensors/index'

/** One composure/gaze sample from the face pipeline (every ~2 s). */
export interface FaceSample {
  composure: Composure
  gaze: Gaze
  /** composure score 0..1 (1 = perfectly composed) */
  score: number
  blinkRate?: number
  brow?: number
  gazeX?: number
  faceDetected?: boolean
}

/** One voice-stress sample (0..1) from the microphone analyser. */
export interface VoiceSample {
  stress: number
}

/** Samples older than this are not attached to a turn. */
export const SAMPLE_TTL_MS = 15_000

export interface SensorsState {
  consent: boolean
  enabled: boolean
  starting: boolean
  error: string | null
  composure: Composure | null
  composureScore: number | null
  gaze: Gaze | null
  voiceStress: number | null
  lastSampleAt: number | null
  lastVoiceAt: number | null
  /** The Investigation lane sets this when the Evidence tab is open so gaze "right" maps to `evidence`. */
  evidenceTabOpen: boolean

  setConsent: (v: boolean) => void
  /** Ask for the camera and start the face pipeline. Resolves true when running. */
  start: () => Promise<boolean>
  stop: () => void
  /** Start voice-stress sampling on an open mic stream (during STT). Returns a stop function. */
  startVoice: (stream: MediaStream) => () => void
  signal: () => PlayerSignal | undefined
  onFaceSample: (s: FaceSample) => void
  onVoiceSample: (s: VoiceSample) => void
  clearVoiceStress: () => void
  setEvidenceTabOpen: (v: boolean) => void
}

let videoEl: HTMLVideoElement | null = null
let stream: MediaStream | null = null
let stopVoice: (() => void) | null = null

function releaseMedia(): void {
  try {
    stopFace()
  } catch {
    /* ignore */
  }
  try {
    stopVoice?.()
  } catch {
    /* ignore */
  }
  stopVoice = null
  if (stream) {
    for (const track of stream.getTracks()) {
      try {
        track.stop()
      } catch {
        /* ignore */
      }
    }
    stream = null
  }
  if (videoEl) {
    try {
      videoEl.pause()
      videoEl.srcObject = null
      videoEl.remove()
    } catch {
      /* ignore */
    }
    videoEl = null
  }
}

export const useSensors = create<SensorsState>()((set, get) => ({
  consent: false,
  enabled: false,
  starting: false,
  error: null,
  composure: null,
  composureScore: null,
  gaze: null,
  voiceStress: null,
  lastSampleAt: null,
  lastVoiceAt: null,
  evidenceTabOpen: false,

  setConsent: (v) => {
    set({ consent: v, error: null })
    if (!v && get().enabled) get().stop()
  },

  start: async () => {
    const s = get()
    if (s.enabled) return true
    if (s.starting) return false
    if (!s.consent) {
      set({ error: 'Camera consent is required before sensors can start.' })
      return false
    }
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      set({ error: 'This browser does not support camera access.' })
      return false
    }
    set({ starting: true, error: null })
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user', frameRate: { ideal: 15 } },
        audio: false,
      })
      const video = document.createElement('video')
      video.setAttribute('aria-hidden', 'true')
      video.setAttribute('playsinline', '')
      video.muted = true
      video.autoplay = true
      Object.assign(video.style, { position: 'fixed', width: '1px', height: '1px', opacity: '0', pointerEvents: 'none', left: '-10px', top: '-10px' })
      video.srcObject = stream
      document.body.appendChild(video)
      videoEl = video
      try {
        await video.play()
      } catch {
        /* autoplay may be deferred; the pipeline reads frames when available */
      }
      await startFace(video, (sample) => get().onFaceSample(sample))
      set({ enabled: true, starting: false, error: null })
      return true
    } catch (e) {
      releaseMedia()
      const msg = e instanceof DOMException && (e.name === 'NotAllowedError' || e.name === 'SecurityError') ? 'Camera permission was denied.' : e instanceof Error && e.message ? e.message : 'Could not start the camera.'
      set({ enabled: false, starting: false, error: msg })
      return false
    }
  },

  stop: () => {
    releaseMedia()
    set({ enabled: false, starting: false, composure: null, composureScore: null, gaze: null, voiceStress: null, lastSampleAt: null, lastVoiceAt: null })
  },

  startVoice: (micStream) => {
    try {
      stopVoice?.()
    } catch {
      /* ignore */
    }
    const stop = startVoiceStress(micStream, (sample) => get().onVoiceSample(sample))
    stopVoice = stop
    return () => {
      try {
        stop()
      } finally {
        if (stopVoice === stop) stopVoice = null
      }
    }
  },

  signal: () => {
    const s = get()
    if (!s.enabled && s.voiceStress == null) return undefined
    const now = Date.now()
    const out: PlayerSignal = {}
    if (s.enabled && s.composure && s.lastSampleAt != null && now - s.lastSampleAt <= SAMPLE_TTL_MS) out.composure = s.composure
    if (s.enabled && s.gaze && s.lastSampleAt != null && now - s.lastSampleAt <= SAMPLE_TTL_MS) out.gaze = s.gaze
    if (s.voiceStress != null && s.lastVoiceAt != null && now - s.lastVoiceAt <= SAMPLE_TTL_MS * 2) out.voice_stress = Math.max(0, Math.min(1, s.voiceStress))
    return Object.keys(out).length ? out : undefined
  },

  onFaceSample: (sample) => {
    const gaze = sample.gaze === 'notebook' && get().evidenceTabOpen ? 'evidence' : sample.gaze
    set({ composure: sample.composure, composureScore: sample.score, gaze, lastSampleAt: Date.now() })
  },

  onVoiceSample: (sample) => {
    set({ voiceStress: Math.max(0, Math.min(1, sample.stress)), lastVoiceAt: Date.now() })
  },

  clearVoiceStress: () => set({ voiceStress: null, lastVoiceAt: null }),
  setEvidenceTabOpen: (v) => set({ evidenceTabOpen: v }),
}))

/** Label for the ComposureMeter: "Calm" / "Neutral" / "Nervous". */
export function composureLabel(c: Composure | null): string {
  if (c === 'confident') return 'Calm'
  if (c === 'nervous') return 'Nervous'
  if (c === 'neutral') return 'Neutral'
  return '—'
}
