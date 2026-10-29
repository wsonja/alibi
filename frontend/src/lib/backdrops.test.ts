import { describe, expect, it } from 'vitest'
import { backdropUrls, sceneForLocation, sceneForPath } from './backdrops'

describe('backdrops', () => {
  it('maps Vane Hall rooms to painted scenes', () => {
    expect(sceneForLocation('study')).toBe('library')
    expect(sceneForLocation('garden')).toBe('manor_exterior')
    expect(sceneForLocation('darkroom')).toBe('bedroom')
    expect(sceneForLocation(null)).toBe('library')
  })

  it('picks route defaults and builds urls', () => {
    expect(sceneForPath('/')).toBe('manor_exterior')
    expect(sceneForPath('/game/abc/briefing')).toBe('library')
    expect(backdropUrls('library').landscape).toBe('/backdrops/landscape_16x9/library.png')
    expect(backdropUrls('manor_exterior').mobile).toBe('/backdrops/mobile_9x16/manor_exterior.webp')
  })
})
