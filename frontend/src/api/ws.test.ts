import { describe, expect, it } from 'vitest'
import { gameSocketUrls, normalizeWsMessage } from './ws'

const turn = { turn: 3, seq: 0, type: 'ask', actor: 'pell', target: 'pell', spoken: 'Inspector, Inspector.', clock: '00:35' }

describe('normalizeWsMessage', () => {
  it('reads the canonical {type, data} envelope', () => {
    const evt = normalizeWsMessage({ type: 'turn_result', data: turn })
    expect(evt.type).toBe('turn_result')
    if (evt.type === 'turn_result') expect(evt.turn.actor).toBe('pell')
  })

  it('reads a flattened envelope and {event, payload}', () => {
    const flat = normalizeWsMessage({ event: 'confront_line', ...turn, other: 'ada' })
    expect(flat.type).toBe('confront_line')
    if (flat.type === 'confront_line') {
      expect(flat.turn.other).toBe('ada')
      expect(flat.turn.type).toBe('ask') // the turn's own type survives
    }
    const alt = normalizeWsMessage({ event: 'ticker', payload: { text: 'A door closed somewhere upstairs.' } })
    expect(alt).toEqual({ type: 'ticker', text: 'A door closed somewhere upstairs.' })
  })

  it('normalises the small events', () => {
    expect(normalizeWsMessage({ type: 'clock', clock: '01:05' })).toEqual({ type: 'clock', clock: '01:05' })
    expect(normalizeWsMessage({ type: 'confront_done', turn: 7 })).toEqual({ type: 'confront_done', turn: 7 })
    expect(normalizeWsMessage({ type: 'pending', suspect_id: 'ada' })).toEqual({ type: 'pending', suspect_id: 'ada' })
    const nb = normalizeWsMessage({ type: 'notebook_updated', data: { turn: 2, per_suspect: [], contradictions: [], suggested_next: [] } })
    expect(nb.type).toBe('notebook_updated')
    if (nb.type === 'notebook_updated') expect(nb.notebook.turn).toBe(2)
    const we = normalizeWsMessage({ type: 'world_event', text: 'Smoke from the study.', evidence: { id: 'ashes_in_grate', name: 'Burned papers', location: 'study', state: 'known', description: 'ash' } })
    expect(we.type).toBe('world_event')
    if (we.type === 'world_event') expect(we.evidence?.id).toBe('ashes_in_grate')
  })

  it('never throws on garbage', () => {
    expect(normalizeWsMessage(null).type).toBe('unknown')
    expect(normalizeWsMessage('hello').type).toBe('unknown')
    expect(normalizeWsMessage({ type: 'turn_result', data: { nope: true } }).type).toBe('unknown')
    expect(normalizeWsMessage({ type: 'something_new', x: 1 }).type).toBe('unknown')
  })

  it('builds ws urls from the API base', () => {
    const urls = gameSocketUrls('abc def')
    expect(urls[0]).toMatch(/^ws:\/\/.+\/api\/ws\/games\/abc%20def$/)
    expect(urls[1]).toMatch(/^ws:\/\/.+\/ws\/games\/abc%20def$/)
  })
})
