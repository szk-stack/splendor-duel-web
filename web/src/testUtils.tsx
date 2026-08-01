/** 测试共享 fixture：构造 GameState / PlayerView。 */
import type { GameState, LegalActions, PlayerView } from './types'

export function makePlayer(overrides: Partial<PlayerView> = {}): PlayerView {
  return {
    slot: 0,
    nickname: 'A',
    tokens: { white: 0, blue: 0, green: 0, red: 0, black: 0, pearl: 0, gold: 0 },
    privileges: 0,
    points: 0,
    crowns: 0,
    bought: [],
    royal_cards: [],
    reserved: [],
    reserved_count: 0,
    ...overrides,
  }
}

export function makeGameState(overrides: Partial<GameState> = {}): GameState {
  const me = makePlayer({ slot: 0, nickname: 'A' })
  const opp = makePlayer({ slot: 1, nickname: 'B', privileges: 1 })
  return {
    seed: 1,
    board: Array(25).fill('white'),
    pyramid: {
      '1': [null, null, null, null, null],
      '2': [null, null, null, null],
      '3': [null, null, null],
    },
    deck_sizes: { '1': 25, '2': 20, '3': 10 },
    royal_pool: [],
    players: [me, opp],
    current: 0,
    phase: 'optional',
    turn: 0,
    privilege_used: false,
    fill_used: false,
    replay_pending: false,
    winner: null,
    win_reason: null,
    ...overrides,
  }
}

export function makeLegal(actions: LegalActions['actions'] = []): LegalActions {
  return { phase: 'optional', actions }
}
