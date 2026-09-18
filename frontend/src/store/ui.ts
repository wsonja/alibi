/**
 * UI store (docs/INTERFACES.md §7): accessibility flags, judge panel, TTS provider, action tab.
 * The a11y flags are persisted to localStorage (try/catch) and mirrored onto <html data-*> attributes that
 * theme.css hooks into: data-dyslexia, data-low-sensory, data-screen-reader, data-plain-language, data-voice.
 */
import { create } from 'zustand'
import type { AccessibilityPayload } from '@/api/types'
import { loadJSON, saveJSON } from '@/lib/storage'

export interface A11yFlags {
  voice: boolean
  screenReader: boolean
  lowSensory: boolean
  dyslexia: boolean
  plainLanguage: boolean
}

export type A11yKey = keyof A11yFlags
export type ActionTab = 'ask' | 'present' | 'tactic' | 'confront' | 'search'
export type TtsProvider = 'webspeech' | 'elevenlabs'

export const A11Y_OPTIONS: ReadonlyArray<{ key: A11yKey; label: string; icon: string; hint: string }> = [
  { key: 'voice', label: 'Voice play', icon: '🎤', hint: 'Suspects speak their lines; ask by microphone.' },
  { key: 'screenReader', label: 'Screen reader', icon: '🖥', hint: 'Verbose labels and live announcements.' },
  { key: 'lowSensory', label: 'Low-sensory', icon: '🍃', hint: 'No heartbeat, no animation, no urgency colours.' },
  { key: 'dyslexia', label: 'Dyslexia text', icon: 'Aa', hint: 'Hyperlegible font, wider spacing, cream on charcoal.' },
]

const STORAGE_KEY = 'mmm.ui.v1'

interface PersistedUI {
  a11y: A11yFlags
  ttsProvider: TtsProvider
}

const DEFAULT_A11Y: A11yFlags = {
  voice: false,
  screenReader: false,
  lowSensory: false,
  dyslexia: false,
  plainLanguage: false,
}

function envTts(): TtsProvider {
  const v = (import.meta.env.VITE_TTS_PROVIDER ?? '').toLowerCase()
  return v === 'elevenlabs' ? 'elevenlabs' : 'webspeech'
}

function loadPersisted(): PersistedUI {
  const raw = loadJSON<Partial<PersistedUI>>(STORAGE_KEY, {})
  const a11y: A11yFlags = { ...DEFAULT_A11Y }
  if (raw.a11y && typeof raw.a11y === 'object') {
    for (const k of Object.keys(DEFAULT_A11Y) as A11yKey[]) {
      const v = (raw.a11y as Partial<A11yFlags>)[k]
      if (typeof v === 'boolean') a11y[k] = v
    }
  }
  const ttsProvider: TtsProvider = raw.ttsProvider === 'elevenlabs' || raw.ttsProvider === 'webspeech' ? raw.ttsProvider : envTts()
  return { a11y, ttsProvider }
}

/** Mirror the flags onto <html> so CSS can react. Safe to call anywhere (no-op without a DOM). */
export function applyA11yAttributes(a11y: A11yFlags): void {
  if (typeof document === 'undefined') return
  const el = document.documentElement
  const set = (attr: string, on: boolean) => {
    if (on) el.setAttribute(attr, '')
    else el.removeAttribute(attr)
  }
  set('data-dyslexia', a11y.dyslexia)
  set('data-low-sensory', a11y.lowSensory)
  set('data-screen-reader', a11y.screenReader)
  set('data-plain-language', a11y.plainLanguage)
  set('data-voice', a11y.voice)
}

export interface UIState {
  a11y: A11yFlags
  judgeOpen: boolean
  ttsProvider: TtsProvider
  actionTab: ActionTab
  /** True once the store has applied persisted flags to the document. */
  hydrated: boolean

  setA11y: (patch: Partial<A11yFlags>) => void
  toggleA11y: (key: A11yKey) => void
  setJudgeOpen: (open: boolean) => void
  toggleJudge: () => void
  setTtsProvider: (p: TtsProvider) => void
  setActionTab: (tab: ActionTab) => void
  /** The `accessibility` JSON sent with POST /games (camera flag added by the caller). */
  accessibilityPayload: (camera: boolean) => AccessibilityPayload
}

const initial = loadPersisted()

export const useUI = create<UIState>()((set, get) => ({
  a11y: initial.a11y,
  judgeOpen: false,
  ttsProvider: initial.ttsProvider,
  actionTab: 'ask',
  hydrated: false,

  setA11y: (patch) => set((s) => ({ a11y: { ...s.a11y, ...patch } })),
  toggleA11y: (key) => set((s) => ({ a11y: { ...s.a11y, [key]: !s.a11y[key] } })),
  setJudgeOpen: (open) => set({ judgeOpen: open }),
  toggleJudge: () => set((s) => ({ judgeOpen: !s.judgeOpen })),
  setTtsProvider: (p) => set({ ttsProvider: p }),
  setActionTab: (tab) => set({ actionTab: tab }),
  accessibilityPayload: (camera) => {
    const a = get().a11y
    return {
      voice: a.voice,
      screen_reader: a.screenReader,
      low_sensory: a.lowSensory,
      dyslexia: a.dyslexia,
      plain_language: a.plainLanguage,
      camera,
    }
  },
}))

// Persist + mirror to <html> whenever the flags change.
useUI.subscribe((state, prev) => {
  if (state.a11y !== prev.a11y || state.ttsProvider !== prev.ttsProvider) {
    saveJSON(STORAGE_KEY, { a11y: state.a11y, ttsProvider: state.ttsProvider } satisfies PersistedUI)
  }
  if (state.a11y !== prev.a11y) applyA11yAttributes(state.a11y)
})

// Apply once at module load so the first paint already has the right attributes.
applyA11yAttributes(initial.a11y)
useUI.setState({ hydrated: true })

/** Selector helpers. */
export const selectA11y = (s: UIState) => s.a11y
export const selectLowSensory = (s: UIState) => s.a11y.lowSensory
