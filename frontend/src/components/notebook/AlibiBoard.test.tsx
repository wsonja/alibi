// @vitest-environment jsdom
import { act, type ReactElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import type { NotebookEntry } from '@/api/types'
import { AlibiBoard } from './AlibiBoard'

const CAST = [
  { id: 'margaret', name: 'Lady Margaret Vane' },
  { id: 'crane', name: 'Dr. Elias Crane' },
  { id: 'ada', name: 'Ada Finch' },
]

const ROOM = 'I was in my room the whole time.'
const GARDEN = 'I only stepped into the garden.'
const PHONE = 'I was on the telephone.'
const KITCHEN = 'I was in the kitchen.'

const NOTEBOOK: NotebookEntry = {
  turn: 4,
  per_suspect: [
    {
      id: 'margaret',
      notes: ['She will not look at the garden door.'],
      claims: [
        { quote: ROOM, where: 'bedroom', from: '23:00', to: '23:30' },
        { quote: GARDEN, where: 'garden', from: '23:00', to: '23:30' },
      ],
    },
    {
      id: 'crane',
      notes: [],
      claims: [{ quote: PHONE, where: 'hall', from: '23:00', to: '23:30' }],
    },
    {
      id: 'ada',
      notes: [],
      claims: [{ quote: KITCHEN, where: 'kitchen', from: '23:00', to: '23:30' }],
    },
  ],
  contradictions: [
    {
      a: { suspect: 'margaret', quote: ROOM },
      b: { suspect_or_evidence: 'margaret', quote: GARDEN },
      note: 'Margaret places herself in the bedroom and the garden at the same time.',
    },
    {
      a: { suspect: 'crane', quote: PHONE },
      b: { suspect_or_evidence: 'ledger', quote: 'The ledger puts Crane in the study.' },
      note: 'The ledger puts Crane in the study, not on the telephone.',
    },
  ],
  suggested_next: ['Confront Margaret and Crane about the garden.'],
}

const TIMELINE = [
  { time: '22:30', event: 'Dinner ends.' },
  { time: '23:00', event: 'Lady Margaret excuses herself.' },
  { time: '23:30', event: 'The necklace breaks.' },
]

let container: HTMLDivElement
let root: Root | null = null

beforeAll(() => {
  ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
})

function render(el: ReactElement) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root!.render(el)
  })
}

afterEach(() => {
  if (root) act(() => root!.unmount())
  root = null
  container?.remove()
})

function chips(quote: string): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(`[title="${quote}"]`)].filter((el) => el.classList.contains('alibi-chip'))
}

describe('AlibiBoard contradiction highlighting', () => {
  it('marks a self-overlap in amber and a clue conflict in red, and leaves a mere time overlap clean', () => {
    render(<AlibiBoard cast={CAST} notebook={NOTEBOOK} timeline={TIMELINE} />)

    const room = chips(ROOM)
    const garden = chips(GARDEN)
    const phone = chips(PHONE)
    const kitchen = chips(KITCHEN)

    expect(room.length).toBe(2)
    expect(garden.length).toBe(2)
    expect(phone.length).toBe(2)
    expect(kitchen.length).toBe(2)

    for (const el of [...room, ...garden]) {
      expect(el.getAttribute('data-mark')).toBe('overlap')
      expect(el.className).toContain('alibi-chip--overlap')
      expect(el.textContent).toContain('Overlapping alibi')
    }
    expect(room[0]!.textContent).toContain('bedroom')
    expect(garden[0]!.textContent).toContain('garden')

    for (const el of phone) {
      expect(el.getAttribute('data-mark')).toBe('conflict')
      expect(el.className).toContain('alibi-chip--conflict')
      expect(el.textContent).toContain('Conflicting alibi')
      expect(el.textContent).toContain('hall')
    }

    for (const el of kitchen) {
      expect(el.getAttribute('data-mark')).toBe('clean')
      expect(el.className).not.toContain('alibi-chip--overlap')
      expect(el.className).not.toContain('alibi-chip--conflict')
      expect(el.textContent).not.toContain('Overlapping')
      expect(el.textContent).not.toContain('Conflicting')
    }

    const headers = [...container.querySelectorAll('thead th')].map((th) => th.textContent)
    expect(headers).toContain('23:00')
    expect(headers).toContain('23:30')
    expect(headers).not.toContain('22:30')

    expect(container.textContent).toContain('Margaret places herself in the bedroom and the garden at the same time.')
    expect(container.textContent).toContain('The ledger puts Crane in the study, not on the telephone.')
  })
})
