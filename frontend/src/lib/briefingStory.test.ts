import { describe, expect, it } from 'vitest'
import { advanceStory, initialProgress } from './briefingStory'

const TIMELINE = [
  { time: '22:30', event: 'a' },
  { time: '22:45', event: 'b' },
  { time: '23:00', event: 'c' },
]

describe('advanceStory', () => {
  it('walks what → victim → timeline pops → meet → evidence → ready', () => {
    let p = initialProgress()
    expect(p.chapter).toBe('what')
    p = advanceStory(p, TIMELINE, 2)
    expect(p.chapter).toBe('victim')
    p = advanceStory(p, TIMELINE, 2)
    expect(p.chapter).toBe('timeline')
    expect(p.timelineShown).toBe(1)
    p = advanceStory(p, TIMELINE, 2)
    expect(p.timelineShown).toBe(2)
    p = advanceStory(p, TIMELINE, 2)
    expect(p.timelineShown).toBe(3)
    p = advanceStory(p, TIMELINE, 2)
    expect(p.chapter).toBe('meet')
    expect(p.meetIndex).toBe(0)
    p = advanceStory(p, TIMELINE, 2)
    expect(p.meetIndex).toBe(1)
    p = advanceStory(p, TIMELINE, 2)
    expect(p.chapter).toBe('evidence')
    p = advanceStory(p, TIMELINE, 2)
    expect(p.chapter).toBe('ready')
    expect(advanceStory(p, TIMELINE, 2).chapter).toBe('ready')
  })
})
