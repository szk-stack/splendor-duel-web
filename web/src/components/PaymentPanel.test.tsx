/** 支付面板测试：数量不足时确认按钮置灰（用户反馈 bug 回归）。 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PaymentPanel } from './PaymentPanel'
import type { CardData, GameState, PlayerView } from '../types'

const card: CardData = {
  id: 'carte_x', level: 1, points: 1, bonus: 'red', bonus_number: 1,
  crowns: 0, capacity: null,
  cost: { white: 3, blue: 0, green: 0, red: 0, black: 0, pearl: 0 },
}

function makeMe(overrides: Partial<PlayerView> = {}): PlayerView {
  return {
    slot: 0, nickname: 'A',
    tokens: { white: 2, blue: 0, green: 0, red: 0, black: 0, pearl: 0, gold: 1 },
    privileges: 0, points: 0, crowns: 0, bought: [], royal_cards: [], reserved: [],
    reserved_count: 0,
    ...overrides,
  }
}

function makeState(): GameState {
  const me = makeMe()
  const opp = makeMe({ slot: 1, nickname: 'B' })
  return {
    seed: 1,
    board: Array(25).fill('white'),
    pyramid: { '1': [null], '2': [null], '3': [null] },
    deck_sizes: { '1': 0, '2': 0, '3': 0 },
    royal_pool: [],
    players: [me, opp],
    current: 0, phase: 'optional', turn: 0,
    privilege_used: false, fill_used: false, replay_pending: false,
    winner: null, win_reason: null,
  }
}

describe('PaymentPanel', () => {
  it('默认支付足额时按钮可用', () => {
    const onConfirm = vi.fn()
    render(
      <PaymentPanel card={card} me={makeMe()} gameState={makeState()}
        royalRequired={false} onConfirm={onConfirm} onCancel={() => {}} />,
    )
    expect(screen.getByRole('button', { name: '确认购买' })).toBeEnabled()
  })

  it('调低筹码数量至不足时按钮置灰并提示', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <PaymentPanel card={card} me={makeMe()} gameState={makeState()}
        royalRequired={false} onConfirm={onConfirm} onCancel={() => {}} />,
    )
    // 白色筹码默认 tokens=2, gold=1；减 1 筹码 -> 2 < 3 不足
    await user.click(screen.getByLabelText('减少white筹码'))
    expect(screen.getByRole('button', { name: '确认购买' })).toBeDisabled()
    expect(screen.getByText('筹码支付不足')).toBeInTheDocument()
  })
})
