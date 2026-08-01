/**
 * 与 server/app/protocol.py 及 docs/protocol.md 三处同步的协议类型。
 * 改协议必须同时改这三处。
 */

export type TokenColor = 'white' | 'blue' | 'green' | 'red' | 'black' | 'pearl' | 'gold'

export const GEM_COLORS: TokenColor[] = ['white', 'blue', 'green', 'red', 'black']

export interface CardData {
  id: string
  level: number
  points: number
  bonus: TokenColor | 'joker' | null
  bonus_number: number
  crowns: number
  capacity: string | null
  cost: Record<string, number>
}

export interface RoyalData {
  id: string
  points: number
  capacity: string | null
}

export interface BoughtEntry {
  id: string
  bonus: TokenColor | null
  bonus_number: number
  points: number
  stacked_on: string | null
}

export interface PlayerView {
  slot: number
  nickname: string
  tokens: Record<TokenColor, number>
  privileges: number
  points: number
  crowns: number
  bought: BoughtEntry[]
  royal_cards: string[]
  reserved: CardData[]
  reserved_count: number
}

export interface GameState {
  seed: number
  board: (TokenColor | null)[]
  pyramid: Record<string, (CardData | null)[]>
  deck_sizes: Record<string, number>
  royal_pool: RoyalData[]
  players: PlayerView[]
  current: number
  phase: string
  turn: number
  privilege_used: boolean
  fill_used: boolean
  replay_pending: boolean
  winner: number | null
  win_reason: string | null
}

// ---------------- 行动 ----------------

export interface BuyOption {
  card: CardData
  source: 'pyramid' | 'reserved'
  tier?: number
  slot?: number
  card_id?: string
  stack_targets?: string[]
}

export type LegalAction =
  | { kind: 'use_privilege'; cells: number[] }
  | { kind: 'fill_board' }
  | { kind: 'force_fill' }
  | { kind: 'take_tokens'; cells: number[] }
  | { kind: 'reserve'; gold_cells: number[]; pyramid: Record<string, number[]>; decks: number[] }
  | { kind: 'buy'; options: BuyOption[] }

export interface LegalActions {
  phase: string
  actions?: LegalAction[]
  discard?: { over: number; hand: Record<string, number> }
}

export interface Payment {
  [color: string]: { tokens: number; gold: number }
}

export interface Action {
  kind: string
  [key: string]: unknown
}

// ---------------- 消息 ----------------

export interface HelloMsg {
  type: 'hello'
  slot: number
  opponent_nickname: string | null
  started: boolean
}

export interface StateMsg {
  type: 'state'
  state: GameState
  legal_actions: LegalActions | null
  events: unknown[]
  started: boolean
}

export interface ErrorMsg {
  type: 'error'
  code: string
  message: string
  ref_action?: unknown
}

export type ServerMessage =
  | HelloMsg
  | StateMsg
  | { type: 'player_joined'; slot: number; nickname: string }
  | { type: 'player_left'; slot: number }
  | { type: 'opponent_reconnected'; slot: number }
  | ErrorMsg
  | { type: 'pong' }

export type ClientMessage =
  | { type: 'hello'; nickname: string }
  | { type: 'action'; action: Action }
  | { type: 'ping' }
