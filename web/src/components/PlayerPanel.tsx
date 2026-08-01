/** 玩家面板：得分/皇冠/特权/手牌/已购卡/保留牌。 */
import type { BoughtEntry, CardData, PlayerView, TokenColor } from '../types'
import { CAPACITY_LABEL, TOKEN_LABEL } from '../api'
import { chipClass, CrownIcon } from './gem'
import { CardView } from './Card'

/** 已购卡按奖励色分组计数（无色卡不显示，只计分；百搭卡已按复制色入账） */
function groupedBought(bought: BoughtEntry[]): { bonus: string; count: number }[] {
  const m = new Map<string, number>()
  for (const e of bought) {
    if (e.bonus === null) continue
    m.set(e.bonus, (m.get(e.bonus) ?? 0) + 1)
  }
  return [...m.entries()].map(([bonus, count]) => ({ bonus, count }))
}

/** 各奖励色得分合计（同色 10 分获胜条件参考） */
function colorPointsOf(bought: BoughtEntry[]): { bonus: string; points: number }[] {
  const m = new Map<string, number>()
  for (const e of bought) {
    if (e.bonus === null) continue
    m.set(e.bonus, (m.get(e.bonus) ?? 0) + e.points)
  }
  return [...m.entries()]
    .map(([bonus, points]) => ({ bonus, points }))
    .sort((a, b) => b.points - a.points)
}

interface Props {
  player: PlayerView
  isMe: boolean
  isCurrent: boolean
  reservedClickable?: (card: CardData) => boolean
  onReservedClick?: (card: CardData) => void
}

export function PlayerPanel({ player, isMe, isCurrent, reservedClickable, onReservedClick }: Props) {
  const colors = Object.keys(player.tokens) as TokenColor[]
  const colorPoints = colorPointsOf(player.bought)
  return (
    <div className={['player-panel', isCurrent ? 'player-current' : '', isMe ? 'me' : 'opp'].join(' ')}>
      <div className="player-body">
        {/* 左侧：名字/手牌/已购卡连续排列 */}
        <div className="player-left">
          <span className="player-name">
            {player.nickname || `玩家${player.slot + 1}`}
            {isMe && <span className="player-me-tag">（我）</span>}
            {player.is_ai && <span className="player-ai-tag">🤖 AI</span>}
          </span>
          <div className="player-tokens">
            {colors.map((c) =>
              player.tokens[c] > 0 ? (
                <span key={c} className={`hand-chip ${chipClass(c)}`}>
                  <b>{player.tokens[c]}</b>
                </span>
              ) : null,
            )}
          </div>
          <div className="player-cards">
            {/* 已购卡按奖励色汇总：数字 = 该色卡牌张数（无色卡不显示只计分） */}
            {groupedBought(player.bought).map(({ bonus, count }) => (
              <span
                key={bonus}
                className={`bought-mini ${bonus === 'white' ? 'bought-mini-light' : ''}`}
                title={`${bonus === 'gray' ? '灰色卡' : `${TOKEN_LABEL[bonus as TokenColor]}奖励卡`} ×${count}`}
              >
                <div className={`bought-mini-gem card-theme-${bonus}`} />
                <b>{count}</b>
              </span>
            ))}
          </div>
        </div>
        {/* 右侧：统计区（得分/颜色得分/皇家牌） */}
        <div className="player-right">
          <span className="player-stats">
            <span className="stat">得分 <b>{player.points}</b></span>
            <span className="stat">皇冠 <b>{player.crowns}</b> <CrownIcon size={11} /></span>
            <span className="stat">特权 <b>{player.privileges}</b></span>
            <span className="stat">卡牌 <b>{player.bought.length}</b></span>
          </span>
          {/* 各颜色得分（同色 10 分获胜参考）——统计区第二行 */}
          {colorPoints.length > 0 && (
            <div className="player-color-points">
              {colorPoints.map(({ bonus, points }) => (
                <span key={bonus} className={`color-point chip-${bonus}`} title={`${TOKEN_LABEL[bonus as TokenColor]}卡得分`}>
                  {points}
                </span>
              ))}
            </div>
          )}
          {/* 皇家牌：右侧显示分数+能力 */}
          {player.royal_cards.length > 0 && (
            <span className="player-royals" title="皇家牌（3/6 皇冠时获得）">
              {player.royal_cards.map((r) => (
                <span key={r.id} className="royal-chip">
                  <b>{r.points}分</b>
                  {r.capacity && <i>{CAPACITY_LABEL[r.capacity] ?? r.capacity}</i>}
                </span>
              ))}
            </span>
          )}
        </div>
      </div>
      {player.reserved.length > 0 && (
        <div className="player-reserved">
          <span className="reserved-label">保留 {player.reserved_count}</span>
          <div className="reserved-row">
            {player.reserved.map((card) => (
              <CardView
                key={card.id}
                card={card}
                highlight={reservedClickable?.(card)}
                onClick={onReservedClick && reservedClickable?.(card) ? () => onReservedClick(card) : undefined}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
