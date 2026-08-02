/** 对局日志面板渲染测试：各类型文案 + 卡面 + 效果。 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { GameLog } from './GameLog'
import type { CardData, LogEntry } from '../types'

const card: CardData = {
  id: 'carte_8', level: 1, points: 0, bonus: 'red', bonus_number: 1,
  crowns: 1, capacity: null,
  cost: { white: 0, blue: 0, green: 0, red: 0, black: 3, pearl: 0 },
}

// ---- store mock ----
let logEntries: LogEntry[] = []
vi.mock('../store', () => ({
  useGameStore: (selector?: (s: any) => any) => {
    const state = { gameLog: logEntries }
    return selector ? selector(state) : state
  },
  wsClient: { send: vi.fn() },
  restoreSession: () => {},
}))

function setLog(entries: LogEntry[]) {
  logEntries = entries
}

describe('GameLog', () => {
  it('空日志显示提示', () => {
    setLog([])
    render(<GameLog />)
    expect(screen.getByText('暂无操作记录')).toBeInTheDocument()
  })

  it('拿筹码条目', () => {
    setLog([{ player: 'Alice', type: 'take_tokens', turn: 1,
              tokens: { white: 2, red: 1 } }])
    render(<GameLog />)
    expect(screen.getByText(/Alice 拿取了 2钻石、1红宝石/)).toBeInTheDocument()
  })

  it('购买条目含完整卡面', () => {
    setLog([{ player: 'Alice', type: 'buy', turn: 2,
              card, payment: { black: { tokens: 3, gold: 0 } } }])
    const { container } = render(<GameLog />)
    expect(screen.getByText(/Alice 花费了 3黑曜石 购买了/)).toBeInTheDocument()
    // 内嵌完整卡面（CardView：奖励色主题 + 皇冠数）
    const cardEl = container.querySelector('.game-log-entry .card')
    expect(cardEl).not.toBeNull()
    expect(cardEl!.className).toContain('card-theme-red')
    expect(cardEl!.querySelector('.card-crowns')).not.toBeNull()
  })

  it('购买条目含能力效果', () => {
    setLog([{ player: 'Bob', type: 'buy', turn: 3, card,
              effects: ['偷取了对方的1个蓝宝石'] }])
    render(<GameLog />)
    expect(screen.getByText(/发动效果：偷取了对方的1个蓝宝石/)).toBeInTheDocument()
  })

  it('保留条目', () => {
    setLog([{ player: 'Alice', type: 'reserve', turn: 4, card }])
    render(<GameLog />)
    expect(screen.getByText(/Alice 获取了1个金币，保留了/)).toBeInTheDocument()
  })

  it('特权条目', () => {
    setLog([{ player: 'Bob', type: 'use_privilege', turn: 5,
              privileges_used: 2, tokens: { blue: 2 } }])
    render(<GameLog />)
    expect(screen.getByText(/Bob 使用 2 个特权兑换了 2蓝宝石/)).toBeInTheDocument()
  })

  it('皇家卡条目含能力', () => {
    setLog([{ player: 'Alice', type: 'royal', turn: 6, royal_index: 1,
              royal_card: { id: 'carte_4', points: 2, capacity: 'steal_opponent_pawn' },
              effects: ['偷取了对方的1个黑曜石'] }])
    render(<GameLog />)
    expect(screen.getByText(/Alice 获得了第 1 张皇家卡/)).toBeInTheDocument()
    expect(screen.getByText(/发动效果：偷取了对方的1个黑曜石/)).toBeInTheDocument()
  })

  it('补充/弃牌/认输条目', () => {
    setLog([
      { player: 'Bob', type: 'fill_board', turn: 7 },
      { player: 'Alice', type: 'discard', turn: 8, tokens: { white: 1 } },
      { player: 'Bob', type: 'concede', turn: 9 },
    ])
    render(<GameLog />)
    expect(screen.getByText('Bob 补充了棋盘')).toBeInTheDocument()
    expect(screen.getByText(/Alice 弃掉了 1钻石/)).toBeInTheDocument()
    expect(screen.getByText('Bob 认输了')).toBeInTheDocument()
  })
})
