/** 购买支付面板：按颜色微调筹码/金币，处理百搭叠放/偷取/拿指示物/皇家牌选择。 */
import { useMemo, useState } from 'react'
import type { BoughtEntry, CardData, GameState, PlayerView, TokenColor } from '../types'
import { GEM_COLORS } from '../types'
import { defaultPayment, effectiveCost } from '../gameLogic'
import { chipClass } from './gem'

interface Props {
  card: CardData
  me: PlayerView
  gameState: GameState
  stackTargets?: string[]
  royalRequired: boolean
  onConfirm: (payload: Record<string, unknown>) => void
  onCancel: () => void
}

interface ColorPay {
  tokens: number
  gold: number
}

export function PaymentPanel({ card, me, gameState, stackTargets, royalRequired, onConfirm, onCancel }: Props) {
  // 有效费用 = 卡费 - 奖励（同色）
  const effCost = useMemo(() => effectiveCost(card, me.bought), [card, me.bought])

  // 默认支付：先筹码后金币
  const [pay, setPay] = useState<Record<string, ColorPay>>(() => defaultPayment(effCost, me.tokens))

  const [jokerTarget, setJokerTarget] = useState<string>(stackTargets?.[0] ?? '')
  const [stealColor, setStealColor] = useState<string>('')
  const [royalChoice, setRoyalChoice] = useState<string>(gameState.royal_pool[0]?.id ?? '')
  const [takeCell] = useState<string>(() => {
    if (card.capacity !== 'take_on_board' || card.bonus === null) return ''
    const cell = gameState.board.findIndex((t) => t === card.bonus)
    return cell >= 0 ? String(cell) : ''
  })

  const stealable = (Object.keys(me === me ? gameState.players.find((p) => p.slot !== me.slot)!.tokens : {}) as TokenColor[])
    .filter((c) => c !== 'gold' && gameState.players.find((p) => p.slot !== me.slot)!.tokens[c] > 0)

  const goldUsed = Object.values(pay).reduce((s, p) => s + p.gold, 0)

  const setColor = (color: string, field: 'tokens' | 'gold', delta: number) => {
    setPay((prev) => {
      const cur = prev[color] ?? { tokens: 0, gold: 0 }
      const max = field === 'tokens' ? me.tokens[color as TokenColor] ?? 0 : me.tokens.gold
      return {
        ...prev,
        [color]: { ...cur, [field]: Math.max(0, Math.min(max, cur[field] + delta)) },
      }
    })
  }

  const submit = () => {
    const payment: Record<string, { tokens: number; gold: number }> = {}
    for (const color of [...GEM_COLORS, 'pearl']) payment[color] = pay[color] ?? { tokens: 0, gold: 0 }
    const payload: Record<string, unknown> = { payment }
    if (card.bonus === 'joker') payload.joker_target = jokerTarget
    if (card.capacity === 'steal_opponent_pawn' && stealColor) payload.steal_color = stealColor
    if (card.capacity === 'take_on_board' && takeCell) payload.take_cell = Number(takeCell)
    if (royalRequired) payload.royal_choice = royalChoice
    onConfirm(payload)
  }

  return (
    <div className="payment-panel">
      <h4>购买 {card.id}</h4>
      {([...GEM_COLORS, 'pearl'] as TokenColor[]).map((color) =>
        effCost[color] > 0 || (pay[color]?.tokens ?? 0) > 0 || (pay[color]?.gold ?? 0) > 0 ? (
          <div key={color} className="pay-row">
            <span className={chipClass(color)} />
            <span className="pay-need">需 {effCost[color]}</span>
            <div className="pay-steppers">
              <span>
                筹码 <button onClick={() => setColor(color, 'tokens', -1)}>−</button>
                <b>{pay[color]?.tokens ?? 0}</b>
                <button onClick={() => setColor(color, 'tokens', 1)}>+</button>
              </span>
              <span>
                金币 <button onClick={() => setColor(color, 'gold', -1)}>−</button>
                <b>{pay[color]?.gold ?? 0}</b>
                <button onClick={() => setColor(color, 'gold', 1)}>+</button>
              </span>
            </div>
          </div>
        ) : null,
      )}
      <div className="pay-gold-sum">金币使用合计：{goldUsed} / {me.tokens.gold}</div>

      {card.bonus === 'joker' && stackTargets && (
        <label className="pay-option">
          叠放到：
          <select value={jokerTarget} onChange={(e) => setJokerTarget(e.target.value)}>
            {stackTargets.map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </label>
      )}

      {card.capacity === 'steal_opponent_pawn' && stealable.length > 0 && (
        <label className="pay-option">
          偷取颜色：
          <select value={stealColor} onChange={(e) => setStealColor(e.target.value)}>
            <option value="">不偷（对手无可偷时自动忽略）</option>
            {stealable.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
      )}

      {card.capacity === 'take_on_board' && takeCell !== '' && (
        <label className="pay-option">
          拿取棋盘指示物：<span className="muted">已选第 {takeCell} 格（奖励色）</span>
        </label>
      )}

      {royalRequired && (
        <label className="pay-option">
          获得皇家牌：
          <select value={royalChoice} onChange={(e) => setRoyalChoice(e.target.value)}>
            {gameState.royal_pool.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id}（{r.points} 分{r.capacity ? `，${r.capacity}` : ''}）
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="pay-actions">
        <button className="action-btn action-btn-confirm" onClick={submit}>确认购买</button>
        <button className="action-btn" onClick={onCancel}>取消</button>
      </div>
    </div>
  )
}

// 供 Game 复用的能力说明
export const ROYAL_THRESHOLDS = [3, 6]
export type { BoughtEntry }
