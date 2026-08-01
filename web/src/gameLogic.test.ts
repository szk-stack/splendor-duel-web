/** 前端交互逻辑单元测试（与服务端一致的规则引导）。 */
import { describe, expect, it } from 'vitest'
import type { BoughtEntry, CardData } from './types'
import {
  inLine,
  changeDiscard,
  effectiveCost,
  defaultPayment,
  toggleTakeCell,
  bonusOf,
  paymentValid,
} from './gameLogic'

describe('inLine 格位成线判定', () => {
  // 5x5 行主序：0-4 第一行, 5-9 第二行...
  it('1 个格恒为真', () => {
    expect(inLine([7])).toBe(true)
  })
  it('横向成线', () => {
    expect(inLine([1, 2])).toBe(true)
    expect(inLine([1, 2, 3])).toBe(true)
  })
  it('纵向成线', () => {
    expect(inLine([1, 6, 11])).toBe(true)
  })
  it('斜向成线', () => {
    expect(inLine([0, 6, 12])).toBe(true)
    expect(inLine([4, 8, 12])).toBe(true)
  })
  it('不成线被拒', () => {
    expect(inLine([0, 2])).toBe(false)
    expect(inLine([0, 1, 7])).toBe(false)
    expect(inLine([0, 1, 6])).toBe(false)
  })
  it('同行相邻但跨行被拒（第 4/5 格边界）', () => {
    expect(inLine([3, 4, 5])).toBe(false)
  })
  it('乱序点击同一列仍成线（用户场景：15→20→10）', () => {
    expect(inLine([15, 20, 10])).toBe(true)
    expect(inLine([4, 12, 8])).toBe(true)  // 斜线乱序
    expect(inLine([7, 5, 6])).toBe(true)   // 横向乱序
  })
})

describe('changeDiscard 弃牌选择增减', () => {
  it('增加不超过持有量', () => {
    expect(changeDiscard({}, 'red', 1, 3)).toEqual({ red: 1 })
    expect(changeDiscard({ red: 3 }, 'red', 1, 3)).toEqual({ red: 3 })
  })
  it('减少可到 0 并删除键', () => {
    expect(changeDiscard({ red: 2 }, 'red', -1, 5)).toEqual({ red: 1 })
    expect(changeDiscard({ red: 1 }, 'red', -1, 5)).toEqual({})
  })
  it('多颜色互不影响', () => {
    let s = changeDiscard({}, 'red', 1, 5)
    s = changeDiscard(s, 'blue', 2, 5)
    s = changeDiscard(s, 'red', -1, 5)
    expect(s).toEqual({ blue: 2 })
  })
})

describe('effectiveCost 奖励减免', () => {
  const card = {
    id: 'carte_8', level: 1, points: 0, bonus: 'red' as const, bonus_number: 1,
    crowns: 1, capacity: null,
    cost: { white: 0, blue: 0, green: 0, red: 0, black: 3, pearl: 0 },
  } satisfies CardData
  it('无奖励时按原价', () => {
    expect(effectiveCost(card, []).black).toBe(3)
  })
  it('红奖励只减红费用，不减黑', () => {
    const bought: BoughtEntry[] = [{ id: 'x', bonus: 'red', bonus_number: 1, points: 0, stacked_on: null }]
    expect(effectiveCost(card, bought).black).toBe(3)
  })
  it('黑奖励减黑费用，且不为负', () => {
    const bought: BoughtEntry[] = [{ id: 'x', bonus: 'black', bonus_number: 5, points: 0, stacked_on: null }]
    expect(effectiveCost(card, bought).black).toBe(0)
  })
  it('珍珠费用不减免', () => {
    const card2: CardData = { ...card, cost: { ...card.cost, black: 0, pearl: 1 } }
    const bought: BoughtEntry[] = [{ id: 'x', bonus: 'pearl', bonus_number: 2, points: 0, stacked_on: null }]
    expect(effectiveCost(card2, bought).pearl).toBe(1)
  })
})

describe('bonusOf 奖励统计', () => {
  it('百搭卡按复制色计入（stacked_on 卡的颜色）', () => {
    const bought: BoughtEntry[] = [
      { id: 'a', bonus: 'blue', bonus_number: 1, points: 0, stacked_on: null },
      { id: 'b', bonus: 'red', bonus_number: 2, points: 0, stacked_on: null },
      { id: 'c', bonus: null, bonus_number: 0, points: 3, stacked_on: null },
    ]
    expect(bonusOf(bought)).toEqual({ blue: 1, red: 2 })
  })
})

describe('defaultPayment 默认支付', () => {
  const tokens = { white: 2, blue: 0, green: 0, red: 0, black: 0, pearl: 1, gold: 2 }
  it('先筹码后金币', () => {
    const cost = { white: 3, blue: 0, green: 0, red: 0, black: 0, pearl: 0 }
    const p = defaultPayment(cost, tokens)
    expect(p.white).toEqual({ tokens: 2, gold: 1 })
  })
  it('金币不足时按持有量封顶', () => {
    const cost = { white: 10, blue: 0, green: 0, red: 0, black: 0, pearl: 0 }
    const p = defaultPayment(cost, tokens)
    expect(p.white).toEqual({ tokens: 2, gold: 2 })
  })
  it('珍珠费用由珍珠或金币支付', () => {
    const cost = { white: 0, blue: 0, green: 0, red: 0, black: 0, pearl: 2 }
    const p = defaultPayment(cost, tokens)
    expect(p.pearl).toEqual({ tokens: 1, gold: 1 })
  })
})

describe('toggleTakeCell 拿筹码选择', () => {
  it('点选与取消', () => {
    expect(toggleTakeCell([], 1)).toEqual([1])
    expect(toggleTakeCell([1], 1)).toEqual([])
  })
  it('最多 3 个', () => {
    expect(toggleTakeCell([0, 1, 2], 6)).toEqual([0, 1, 2])
  })
  it('不成线的新格被拒', () => {
    expect(toggleTakeCell([0, 2], 7)).toEqual([0, 2])
  })
  it('乱序点同一列 3 格可成组（用户场景：15→20→10）', () => {
    let sel = toggleTakeCell([], 15)
    sel = toggleTakeCell(sel, 20)
    sel = toggleTakeCell(sel, 10)
    expect(sel).toEqual([15, 20, 10])
  })
})

describe('paymentValid 支付有效性（不足时按钮置灰）', () => {
  const eff = { white: 3, blue: 0, green: 0, red: 0, black: 0, pearl: 0 }
  it('足额支付有效', () => {
    const pay = { white: { tokens: 2, gold: 1 } }
    expect(paymentValid(pay, eff, 2)).toBe(true)
  })
  it('数量不足无效', () => {
    const pay = { white: { tokens: 1, gold: 1 } }
    expect(paymentValid(pay, eff, 2)).toBe(false)
  })
  it('金币合计超出持有量无效', () => {
    const pay = { white: { tokens: 2, gold: 2 } }
    expect(paymentValid(pay, eff, 1)).toBe(false)
  })
  it('费用为 0 的颜色可缺省', () => {
    const pay = { white: { tokens: 3, gold: 0 } }
    expect(paymentValid(pay, eff, 0)).toBe(true)
  })
})
