/** GamePage 集成测试：可选行动（补充棋盘）后界面必须恢复可操作（busy 复位）。 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { GamePage } from './Game'
import { makeGameState, makeLegal } from '../testUtils'

// ---- store mock：可控的全局状态 ----
const sendAction = vi.fn()
let storeState: Record<string, unknown> = {}

vi.mock('../store', () => ({
  useGameStore: (selector?: (s: any) => any) => (selector ? selector(storeState) : storeState),
  wsClient: { send: vi.fn() },
  restoreSession: () => {},
}))

function renderGame() {
  const r = render(
    <MemoryRouter>
      <GamePage />
    </MemoryRouter>,
  )
  return r
}

function setStore(state: Partial<typeof storeState>) {
  storeState = { ...storeState, ...state }
}

describe('GamePage 可选行动后恢复可操作', () => {
  it('补充棋盘（可选行动，回合不变）后按钮恢复可用', async () => {
    const user = userEvent.setup()
    // 我的回合，唯一合法行动是补充棋盘（模拟"无法执行其他行动"场景）
    setStore({
      room: { code: 'ABCDE', token: 't', slot: 0 },
      nickname: 'A',
      connStatus: 'open',
      gameState: makeGameState(),
      legalActions: makeLegal([{ kind: 'fill_board' }]),
      lastEvents: [],
      gameLog: [],
      error: null,
      banner: null,
      sendAction,
      rematch: vi.fn(),
      leave: vi.fn(),
      reset: vi.fn(),
      clearError: vi.fn(),
    })
    const { rerender } = renderGame()

    await user.click(screen.getByRole('button', { name: '补充棋盘' }))
    expect(sendAction).toHaveBeenCalledWith({ kind: 'fill_board' })

    // 服务端广播新状态（可选行动：回合/当前玩家都不变，只有 fill_used 变化）
    setStore({
      gameState: makeGameState({ fill_used: true }),
      legalActions: makeLegal([{ kind: 'take_tokens', cells: [0, 1, 2] }]),
    })
    rerender(
      <MemoryRouter>
        <GamePage />
      </MemoryRouter>,
    )

    // 修复后：busy 复位，行动按钮重新可用
    expect(screen.getByRole('button', { name: '拿筹码' })).toBeEnabled()
  })
})
