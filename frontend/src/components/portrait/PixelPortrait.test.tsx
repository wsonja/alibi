// @vitest-environment jsdom
// Uses react-dom directly (no @testing-library/dom in this install).
import { act, type ReactElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { PixelPortrait } from './PixelPortrait'

const CAST = [
  { id: 'margaret', name: 'Lady Margaret Vane', portrait_prompt: '1920s English aristocratic woman, mid-forties, dark hair pinned up, pearl earrings, high-necked evening dress, composed and cold' },
  { id: 'crane', name: 'Dr. Elias Crane', portrait_prompt: '1920s English country doctor, fifty, grey at the temples, tired kind eyes, tweed waistcoat under a dinner jacket' },
  { id: 'pell', name: 'Thomas Pell', portrait_prompt: '1920s English businessman, early forties, handsome, brilliantined hair, easy confident smile, dinner jacket, cigar' },
  { id: 'ada', name: 'Ada Finch', portrait_prompt: '1920s English housemaid, early twenties, cap and apron, sharp watchful eyes, tired' },
]

let container: HTMLDivElement
let root: Root | null = null

beforeAll(() => {
  ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  // jsdom has no canvas: make getContext return null quietly (the component falls back to SVG)
  HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement['getContext']
})

function render(el: ReactElement) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root!.render(el))
}

afterEach(() => {
  if (root) act(() => root!.unmount())
  root = null
  container?.remove()
})

describe('<PixelPortrait />', () => {
  it('renders every Vane Hall suspect with alt text (SVG fallback when canvas has no 2D context)', () => {
    render(
      <ul>
        {CAST.map((s) => (
          <li key={s.id}>
            <PixelPortrait suspect={s} emotion="nervous" size={96} still />
          </li>
        ))}
      </ul>,
    )
    for (const s of CAST) {
      const img = container.querySelector(`[role="img"][aria-label="Portrait of ${s.name}, looking nervous"]`)
      expect(img, s.name).not.toBeNull()
      expect(img!.getAttribute('data-emotion')).toBe('nervous')
    }
    const svgs = container.querySelectorAll('svg.pixel-portrait')
    expect(svgs.length).toBe(4)
    expect(svgs[0]!.querySelectorAll('rect').length).toBeGreaterThan(100)
    expect(svgs[0]!.querySelector('title')?.textContent).toBe('Portrait of Lady Margaret Vane, looking nervous')
  })

  it('maps unknown emotions to neutral and honours the dim flag', () => {
    render(<PixelPortrait suspect={CAST[3]!} emotion="bewildered" size={56} dim still />)
    const img = container.querySelector('[role="img"]')
    expect(img?.getAttribute('aria-label')).toBe('Portrait of Ada Finch, looking neutral')
    expect(img?.getAttribute('class')).toContain('pixel-portrait--dim')
    expect(img?.getAttribute('width')).toBe('56')
    expect(img?.getAttribute('height')).toBe('65')
  })
})
