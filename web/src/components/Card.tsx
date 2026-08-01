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
          // 皇冠统一右上角（margin-left:auto 在无分数时也靠右）
          <span className="card-crowns">
            {Array.from({ length: card.crowns }).map((_, i) => (
              <CrownIcon key={i} size={14} outline />
            ))}
          </span>
        )}
      </div>
      <div className="card-gem">
        {card.bonus === null ? (
          // 无奖励（灰）卡：虚线空宝石轮廓，表达"不产宝石"
          <span className="card-gem-empty">
            <svg width={24} height={24} viewBox="0 0 20 20" aria-hidden>
              <polygon
                points="10,1 18,6 15,18 5,18 2,6"
                fill="none"
                stroke="#e8e9ef88"
                strokeWidth="1.2"
                strokeDasharray="3 2.5"
              />
            </svg>
            <span>无</span>
          </span>
        ) : (
          /* 双奖励卡直接显示两个宝石图案 */
          <span className="card-gems">
            {Array.from({ length: card.bonus_number }).map((_, i) => (
              <GemIcon
                key={i}
                color={card.bonus}
                size={24}
                dark={card.bonus === 'white' || card.bonus === 'joker'}
              />
            ))}
          </span>
        )}
      </div>
      {/* 宝石下方词条区：百搭标签 / 能力标签，单条时垂直居中 */}
      {(card.bonus === 'joker' || card.capacity) && (
        <div className="card-entries">
          {card.bonus === 'joker' && <span className="card-joker-tag">百搭</span>}
          {card.capacity && (
            <div className="card-capacity">{CAPACITY_LABEL[card.capacity] ?? card.capacity}</div>
          )}
        </div>
      )}
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
