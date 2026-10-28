// @vitest-environment jsdom
import { act, type ReactElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { PaintedPortrait } from './PaintedPortrait'

const MARGARET = { id: 'margaret', name: 'Lady Margaret Vane', portrait_prompt: null }

let container: HTMLDivElement
let root: Root | null = null

beforeAll(() => {
  ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
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

describe('<PaintedPortrait />', () => {
  it('renders the painted avatar for small sizes', () => {
    render(<PaintedPortrait suspect={MARGARET} emotion="nervous" size={56} caseId="vane_hall_1923" />)
    const img = container.querySelector('img')
    expect(img?.getAttribute('src')).toBe('/portraits/vane_hall/margaret_avatar.webp')
    expect(container.querySelector('[aria-label="Portrait of Lady Margaret Vane, looking nervous"]')).not.toBeNull()
  })

  it('requests the emotion bust and falls back to pixel for unknown cast', () => {
    render(<PaintedPortrait suspect={MARGARET} emotion="angry" size={160} caseId="vane_hall_1923" />)
    expect(container.querySelector('img')?.getAttribute('src')).toBe('/portraits/vane_hall/margaret_angry.webp')

    act(() =>
      root!.render(<PaintedPortrait suspect={{ id: 'nobody', name: 'Nobody' }} emotion="neutral" size={96} still />),
    )
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('svg.pixel-portrait, canvas.pixel-portrait')).not.toBeNull()
  })
})
