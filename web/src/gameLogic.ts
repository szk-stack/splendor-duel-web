/**
 * 前端交互逻辑纯函数（客户端只做 UI 引导，最终合法性由服务端校验）。
 * 抽成纯函数便于单元测试。
 */
import type { CardData, PlayerView, TokenColor } from './types'
import { GEM_COLORS } from './types'

/** 格位是否在同一条不间断的直线（横/竖/斜）上，且逐格相邻 */
export function inLine(cells: number[]): boolean {
  if (cells.length <= 1) return true
  const dir = (a: number, b: number) => [
    (a % 5) - (b % 5),
    Math.floor(a / 5) - Math.floor(b / 5),
  ]
  const adjacent = (d: number[]) => Math.abs(d[0]) <= 1 && Math.abs(d[1]) <= 1 && !(d[0] === 0 && d[1] === 0)
  const d = dir(cells[0], cells[1])
  if (!adjacent(d)) return false
  for (let i = 1; i < cells.length - 1; i++) {
    const d2 = dir(cells[i], cells[i + 1])
    if (d[0] !== d2[0] || d[1] !== d2[1] || !adjacent(d2)) return false
  }
  return true
}

/** 弃牌选择：按颜色增减，0 <= 结果 <= 持有量 */
export function changeDiscard(
  prev: Record<string, number>,
  color: string,
  delta: number,
  held: number,
): Record<string, number> {
  const next = { ...prev }
  const val = Math.max(0, Math.min(held, (next[color] ?? 0) + delta))
  if (val === 0) delete next[color]
  else next[color] = val
  return next
}

/** 奖励统计（与服务端一致）：color -> bonus_number 合计 */
export function bonusOf(bought: PlayerView['bought']): Record<string, number> {
  const b: Record<string, number> = {}
  for (const e of bought) if (e.bonus) b[e.bonus] = (b[e.bonus] ?? 0) + e.bonus_number
  return b
}

/** 有效费用 = 卡费 - 同色奖励（珍珠费用永不减免，与服务端一致） */
export function effectiveCost(card: CardData, bought: PlayerView['bought']): Record<string, number> {
  const bonus = bonusOf(bought)
  const c: Record<string, number> = {}
  for (const color of GEM_COLORS) {
    c[color] = Math.max(0, card.cost[color] - (bonus[color] ?? 0))
  }
  c['pearl'] = card.cost['pearl'] ?? 0
  return c
}

/** 默认支付方案：先筹码后金币 */
export function defaultPayment(
  cost: Record<string, number>,
  tokens: Record<TokenColor, number>,
): Record<string, { tokens: number; gold: number }> {
  const p: Record<string, { tokens: number; gold: number }> = {}
  let goldLeft = tokens.gold ?? 0
  for (const color of [...GEM_COLORS, 'pearl']) {
    const need = cost[color] ?? 0
    const t = Math.min(need, tokens[color as TokenColor] ?? 0)
    const g = Math.min(need - t, goldLeft)
    goldLeft -= g
    p[color] = { tokens: t, gold: g }
  }
  return p
}

/** 拿取选择：点选/取消格位，最多 3 个且保持成线 */
export function toggleTakeCell(prev: number[], cell: number): number[] {
  if (prev.includes(cell)) return prev.filter((c) => c !== cell)
  if (prev.length >= 3) return prev
  return inLine([...prev, cell]) ? [...prev, cell] : prev
}

/** 支付明细是否有效：各色筹码+金币 >= 有效费用，且金币合计不超过持有量 */
export function paymentValid(
  pay: Record<string, { tokens: number; gold: number }>,
  effCost: Record<string, number>,
  goldHeld: number,
): boolean {
  let gold = 0
  for (const color of [...GEM_COLORS, 'pearl']) {
    const p = pay[color] ?? { tokens: 0, gold: 0 }
    const need = effCost[color] ?? 0
    if (p.tokens + p.gold < need) return false
    gold += p.gold
  }
  return gold <= goldHeld
}
