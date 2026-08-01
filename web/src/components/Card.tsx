/** 单张卡面：CSS 渐变 + SVG 宝石图标 + 成本/分数/皇冠/能力。 */
import type { CardData } from '../types'
import { CAPACITY_LABEL } from '../api'
import { cardTheme, GemIcon, CrownIcon } from './gem'

const COST_COLOR_LABEL: Record<string, string> = {
  white: '白', blue: '蓝', green: '绿', red: '红', black: '黑', pearl: '珠',
}

interface Props {
  card: CardData
  selected?: boolean
  highlight?: boolean
  dimmed?: boolean
  onClick?: () => void
  showCost?: boolean
}

export function CardView({ card, selected, highlight, dimmed, onClick, showCost = true }: Props) {
  const cls = [
    'card',
    cardTheme(card.bonus),
    selected ? 'card-selected' : '',
    highlight ? 'card-highlight' : '',
    dimmed ? 'card-dimmed' : '',
    onClick ? 'card-clickable' : '',
  ].filter(Boolean).join(' ')

  const costEntries = Object.entries(card.cost).filter(([, n]) => n > 0)

  return (
    <div className={cls} onClick={onClick} title={card.capacity ? CAPACITY_LABEL[card.capacity] : undefined}>
      <div className="card-top">
        {card.points > 0 && <span className="card-points">{card.points}</span>}
        {card.crowns > 0 && (
          <span className="card-crowns">
            {Array.from({ length: card.crowns }).map((_, i) => (
              <CrownIcon key={i} size={12} />
            ))}
          </span>
        )}
      </div>
      <div className="card-gem">
        <GemIcon color={card.bonus} size={26} />
        {card.bonus === 'joker' && <span className="card-joker-tag">百搭</span>}
        {card.bonus_number > 1 && <span className="card-bonus-x">×{card.bonus_number}</span>}
      </div>
      {card.capacity && <div className="card-capacity">{CAPACITY_LABEL[card.capacity] ?? card.capacity}</div>}
      {showCost && (
        <div className="card-cost">
          {costEntries.map(([color, n]) => (
            <span key={color} className={`cost-dot cost-${color}`} title={`${COST_COLOR_LABEL[color]} ×${n}`}>
              {n}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/** 牌背（牌库顶盲保留用） */
export function CardBack({ label }: { label?: string }) {
  return <div className="card card-back">{label ?? '?'}</div>
}
