/**
 * Story beats for the guided Briefing (not a fact sheet).
 * Claimed rooms and intro lines are public-facing only — no secrets.
 */
import type { PublicEvidence, PublicLocation, PublicSuspect, TimelineEntry } from '@/api/types'
import type { BackdropScene } from '@/lib/backdrops'
import { sceneForLocation } from '@/lib/backdrops'
import { extractAlibi } from '@/lib/text'

export type StoryChapter = 'what' | 'victim' | 'timeline' | 'meet' | 'evidence' | 'ready'

/** Where each Vane Hall suspect claims they were (public alibi → nearest painted plate). */
const CLAIMED_SCENE: Record<string, BackdropScene> = {
  margaret: 'bedroom',
  crane: 'dining_room',
  pell: 'dining_room',
  ada: 'dining_room',
}

const CLAIMED_PLACE_LABEL: Record<string, string> = {
  margaret: 'Upstairs — her bedroom',
  crane: 'Away from the drawing room — the telephone',
  pell: 'The billiard room — then his own rooms',
  ada: 'The kitchen',
}

/** Short spoken intro in their public voice (no secrets). */
const INTRO_LINE: Record<string, string> = {
  margaret: 'One had a headache. One went upstairs. That is all one knows of the night.',
  crane: 'I left to telephone a patient in the village, my friend. The line was very poor.',
  pell: 'Stepped out for my cigars, Inspector. Ten minutes. Perhaps less.',
  ada: 'I was in the kitchen with the coffee, sir. Then I found him at his desk.',
}

export function claimedSceneFor(suspectId: string): BackdropScene {
  return CLAIMED_SCENE[suspectId] ?? 'library'
}

export function claimedPlaceLabel(suspectId: string): string {
  return CLAIMED_PLACE_LABEL[suspectId] ?? 'Somewhere in the house'
}

export function introLineFor(suspect: PublicSuspect): string {
  return INTRO_LINE[suspect.id] ?? extractAlibi(suspect.public_description)
}

export function initialEvidence(evidence: PublicEvidence[]): PublicEvidence[] {
  return evidence.filter((e) => e.state === 'known' || e.state === 'examined')
}

export function evidenceScene(ev: PublicEvidence, locations: PublicLocation[]): BackdropScene {
  return sceneForLocation(ev.location ?? locations[0]?.id)
}

export function evidenceLocationName(ev: PublicEvidence, locations: PublicLocation[]): string {
  return locations.find((l) => l.id === ev.location)?.name ?? 'the house'
}

function artPack(caseId: string): string {
  return caseId.startsWith('vane_hall') ? 'vane_hall' : caseId
}

/** Path for a painted object plate; UI falls back to EvidenceIcon when missing. */
export function evidenceArtUrl(caseId: string, evidenceId: string): string {
  return `/evidence/${artPack(caseId)}/${evidenceId}.webp`
}

/** Crime-scene plate for the victim chapter (optional until art lands). */
export function victimArtUrl(caseId: string): string {
  return `/art/${artPack(caseId)}/victim.webp`
}

export interface StoryProgress {
  chapter: StoryChapter
  /** How many timeline rows are visible (1..n). */
  timelineShown: number
  /** Index into cast for the meet chapter. */
  meetIndex: number
}

export function initialProgress(): StoryProgress {
  return { chapter: 'what', timelineShown: 0, meetIndex: 0 }
}

/**
 * Advance one beat. Returns null when the player should use Begin (chapter === ready and they click again is a no-op for advance).
 */
export function advanceStory(
  p: StoryProgress,
  timeline: TimelineEntry[],
  castCount: number,
): StoryProgress {
  switch (p.chapter) {
    case 'what':
      return { ...p, chapter: 'victim' }
    case 'victim':
      return { ...p, chapter: 'timeline', timelineShown: 1 }
    case 'timeline': {
      if (p.timelineShown < timeline.length) {
        return { ...p, timelineShown: p.timelineShown + 1 }
      }
      return { ...p, chapter: 'meet', meetIndex: 0 }
    }
    case 'meet': {
      if (p.meetIndex + 1 < castCount) {
        return { ...p, meetIndex: p.meetIndex + 1 }
      }
      return { ...p, chapter: 'evidence' }
    }
    case 'evidence':
      return { ...p, chapter: 'ready' }
    case 'ready':
      return p
  }
}
