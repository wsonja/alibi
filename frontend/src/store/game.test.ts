import { beforeEach, describe, expect, it } from 'vitest'
import type { GameState, PublicSuspect, PublicTurn } from '@/api/types'
import { applyTurnToCast, describeTurn, mergeTurn, mergeTurns, speakerIndex, turnsForSuspect, upsertEvidence, useGame } from './game'

const suspect = (id: string, name: string): PublicSuspect => ({
  id,
  name,
  role: 'r',
  public_description: 'd',
  portrait_prompt: 'p',
  portrait_url: null,
  stress_pct: 0,
  emotion: 'neutral',
  tell: '',
  silenced: false,
  last_seen_location: 'study',
  voice: null,
})

const t = (turn: number, seq: number, extra: Partial<PublicTurn> = {}): PublicTurn => ({ turn, seq, type: 'ask', actor: 'pell', target: 'pell', clock: '00:20', ...extra })

const game: GameState = {
  game_id: 'g1',
  status: 'investigating',
  turn: 1,
  clock: '00:20',
  case: { id: 'c', title: 'T', setting: 's', briefing: 'b', victim: { name: 'v', description: 'd', cause_of_death_public: 'c' }, timeline_public: [] },
  difficulty: 'detective',
  llm_mode: 'scripted',
  cast: [suspect('margaret', 'Lady Margaret Vane'), suspect('pell', 'Thomas Pell'), suspect('ada', 'Ada Finch')],
  evidence: [{ id: 'decanter', name: 'Decanter', location: 'study', state: 'known', description: 'half empty' }],
  locations: [{ id: 'study', name: 'The Study', description: '', searched: false }],
  turns: [t(1, 0, { actor: 'detective', detective_text: 'Where were you?' })],
  notebook: null,
  ticker: [],
  accessibility: {},
  can_rewind_to: [],
}

describe('merge helpers', () => {
  it('mergeTurn inserts sorted and replaces by (turn, seq)', () => {
    let turns = mergeTurn([], t(2, 1))
    turns = mergeTurn(turns, t(1, 0))
    turns = mergeTurn(turns, t(2, 0))
    expect(turns.map((x) => `${x.turn}:${x.seq}`)).toEqual(['1:0', '2:0', '2:1'])
    turns = mergeTurn(turns, t(2, 0, { spoken: 'replaced' }))
    expect(turns).toHaveLength(3)
    expect(turns[1]?.spoken).toBe('replaced')
    expect(mergeTurns(turns, [t(3, 0), t(3, 1)])).toHaveLength(5)
  })

  it('upsertEvidence adds or patches', () => {
    const list = upsertEvidence(game.evidence, { id: 'decanter', name: 'Decanter', location: 'study', state: 'examined', description: 'half empty', examined_detail: 'bitter almonds' })
    expect(list).toHaveLength(1)
    expect(list[0]?.state).toBe('examined')
    expect(upsertEvidence(list, { id: 'ledger', name: 'Ledger', location: 'study', state: 'known', description: '' })).toHaveLength(2)
  })

  it('applyTurnToCast updates emotion/tell/pressure for the speaking suspect only', () => {
    const cast = applyTurnToCast(game.cast, t(2, 0, { emotion: 'angry', tell: 'goes formal', stress_pct: 40 }))
    expect(cast[1]).toMatchObject({ emotion: 'angry', tell: 'goes formal', stress_pct: 40 })
    expect(cast[0]?.stress_pct).toBe(0)
    expect(applyTurnToCast(game.cast, t(2, 0, { actor: 'detective' }))).toBe(game.cast)
  })

  it('describeTurn / turnsForSuspect / speakerIndex', () => {
    expect(describeTurn(t(2, 0, { spoken: 'I was in bed.', tell: 'blinks' }), game.cast)).toBe('Thomas Pell: I was in bed. (blinks)')
    expect(describeTurn(t(2, 0, { actor: 'detective', detective_text: 'Hm?' }), game.cast)).toBe('You: Hm?')
    expect(turnsForSuspect([t(1, 0, { actor: 'detective', target: 'ada' }), t(1, 1, { actor: 'ada' }), t(2, 0)], 'ada')).toHaveLength(2)
    expect(speakerIndex(game.cast, 'ada')).toBe(2)
    expect(speakerIndex(game.cast, 'nobody')).toBe(0)
  })
})

describe('useGame.applyEvent', () => {
  beforeEach(() => {
    useGame.setState({ gameId: 'g1', game: structuredClone(game), pending: null, confrontation: null, toasts: [], selection: { primary: 'pell', secondary: null }, liveMessage: '' })
  })

  it('merges turn_result, clears pending for that suspect and announces', () => {
    useGame.setState({ pending: { suspectId: 'pell', kind: 'ask', since: 0 } })
    useGame.getState().applyEvent({ type: 'turn_result', turn: t(2, 0, { spoken: 'Inspector, Inspector.', emotion: 'smug', stress_pct: 12, clock: '00:25' }) })
    const s = useGame.getState()
    expect(s.game?.turns).toHaveLength(2)
    expect(s.game?.cast[1]?.emotion).toBe('smug')
    expect(s.game?.clock).toBe('00:25')
    expect(s.game?.turn).toBe(2)
    expect(s.pending).toBeNull()
    expect(s.liveMessage).toContain('Thomas Pell: Inspector, Inspector.')
  })

  it('collects confront_line into the confrontation and tracks the next speaker', () => {
    useGame.setState({ confrontation: { active: true, a: 'pell', b: 'ada', topic: 'gloves', rounds: 3, justWatch: false, lines: [], speaking: 'pell', done: false, startedAt: 0 } })
    useGame.getState().applyEvent({ type: 'confront_line', turn: t(2, 0, { type: 'confront', spoken: 'Tell them, Ada.', other: 'ada' }) })
    let s = useGame.getState()
    expect(s.confrontation?.lines).toHaveLength(1)
    expect(s.confrontation?.speaking).toBe('ada')
    expect(s.pending?.suspectId).toBe('ada')
    useGame.getState().applyEvent({ type: 'confront_done', turn: 2 })
    s = useGame.getState()
    expect(s.confrontation?.done).toBe(true)
    expect(s.pending).toBeNull()
  })

  it('ticker and world events become toasts and update state', () => {
    useGame.getState().applyEvent({ type: 'ticker', text: 'A door closed somewhere upstairs.' })
    useGame.getState().applyEvent({ type: 'world_event', text: 'Smoke from the study.', evidence: { id: 'ashes_in_grate', name: 'Burned papers', location: 'study', state: 'known', description: 'ash' } })
    useGame.getState().applyEvent({ type: 'clock', clock: '01:00' })
    const s = useGame.getState()
    expect(s.toasts.map((x) => x.kind)).toEqual(['ticker', 'world'])
    expect(s.game?.ticker).toEqual(['A door closed somewhere upstairs.', 'Smoke from the study.'])
    expect(s.game?.evidence.map((e) => e.id)).toContain('ashes_in_grate')
    expect(s.game?.clock).toBe('01:00')
  })

  it('select handles primary/secondary (shift-click) rules', () => {
    const { select } = useGame.getState()
    select('ada', true)
    expect(useGame.getState().selection).toEqual({ primary: 'pell', secondary: 'ada' })
    select('ada', true)
    expect(useGame.getState().selection).toEqual({ primary: 'pell', secondary: null })
    select('ada', true)
    select('ada')
    expect(useGame.getState().selection).toEqual({ primary: 'ada', secondary: null })
  })
})
