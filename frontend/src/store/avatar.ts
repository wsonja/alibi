/**
 * Player avatar store: the pixel grid made from the player's photo (lib/avatar.ts), persisted in localStorage.
 * The photo itself is never stored — only this grid of a few hundred palette colours. Read wherever the player
 * appears: the setup page, the "You" rows in the dialogue log, Case Closed.
 */
import { create } from 'zustand'
import { fromAvatarRecord, toAvatarRecord } from '@/lib/avatar'
import type { PortraitGrid } from '@/lib/pixelPortrait'
import { loadJSON, removeKey, saveJSON } from '@/lib/storage'

export const AVATAR_STORAGE_KEY = 'mmm.avatar.v1'

export interface AvatarState {
  grid: PortraitGrid | null
  /** Keep this grid as the avatar (null clears it). */
  setGrid: (grid: PortraitGrid | null) => void
  clear: () => void
}

export const useAvatar = create<AvatarState>()((set) => ({
  grid: fromAvatarRecord(loadJSON<unknown>(AVATAR_STORAGE_KEY, null)),

  setGrid: (grid) => {
    set({ grid })
    if (grid) saveJSON(AVATAR_STORAGE_KEY, toAvatarRecord(grid))
    else removeKey(AVATAR_STORAGE_KEY)
  },

  clear: () => {
    set({ grid: null })
    removeKey(AVATAR_STORAGE_KEY)
  },
}))

export const selectHasAvatar = (s: AvatarState): boolean => s.grid !== null
