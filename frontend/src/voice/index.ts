// placeholder — replaced by the voice lane
// Contract (docs/INTERFACES.md §7): speak(suspect, text, stressPct), stopSpeaking(), useSTT(onFinal).
// This minimal version uses speechSynthesis when available and reports STT as unsupported.
import { useCallback, useState } from 'react'
import type { PublicSuspect } from '@/api/types'

export function speak(suspect: PublicSuspect, text: string, stressPct: number): void {
  if (typeof window === 'undefined' || !('speechSynthesis' in window) || !text) return
  try {
    const u = new SpeechSynthesisUtterance(text)
    const pct = Math.max(0, Math.min(100, stressPct)) / 100
    u.rate = 0.95 + 0.35 * pct
    const base = suspect.voice?.base_pitch ?? 1
    u.pitch = Math.max(0.1, Math.min(2, base + (base >= 1 ? 0.2 : -0.2) * pct))
    const voices = window.speechSynthesis.getVoices()
    const idx = suspect.voice?.webspeech_index
    if (voices.length && typeof idx === 'number') u.voice = voices[idx % voices.length] ?? null
    window.speechSynthesis.speak(u)
  } catch {
    /* ignore */
  }
}

export function stopSpeaking(): void {
  try {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
  } catch {
    /* ignore */
  }
}

export interface STTHandle {
  listening: boolean
  start: () => void
  stop: () => void
  supported: boolean
}

export function useSTT(_onFinal: (text: string) => void): STTHandle {
  const [listening, setListening] = useState(false)
  const start = useCallback(() => setListening(false), [])
  const stop = useCallback(() => setListening(false), [])
  return { listening, start, stop, supported: false }
}
