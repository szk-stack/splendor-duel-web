/** 玩家面板：得分/皇冠/特权/手牌/已购卡/保留牌。 */
import type { CardData, PlayerView, TokenColor } from '../types'
import { CAPACITY_LABEL } from '../api'
import { chipClass, CrownIcon } from './gem'
import { CardView } from './Card'

interface Props {
  player: PlayerView
  isMe: boolean
  isCurrent: boolean
  reservedClickable?: (card: CardData) => boolean
  onReservedClick?: (card: CardData) => void
}

export function PlayerPanel({ player, isMe, isCurrent, reservedClickable, onReservedClick }: Props) {
  const colors = Object.keys(player.tokens) as TokenColor[]
  return (
    <div className={['player-panel', isCurrent ? 'player-current' : '', isMe ? 'me' : 'opp'].join(' ')}>
      <div className="player-head">
        <span className="player-name">
          {player.nickname || `玩家${player.slot + 1}`}
          {isMe && <span className="player-me-tag">（我）</span>}
        </span>
        <span className="player-stats">
          <span className="stat">得分 <b>{player.points}</b></span>
          <span className="stat">皇冠 <b>{player.crowns}</b> <CrownIcon size={11} /></span>
          <span className="stat">特权 <b>{player.privileges}</b></span>
          <span className="stat">卡牌 <b>{player.bought.length}</b></span>
        </span>
      </div>
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
        {player.bought.map((e) => (
          <span
            key={e.id}
            className="bought-mini"
            title={`${e.id} · 奖励 ${e.bonus ?? '无'} · ${e.points} 分 · ${e.crowns ?? 0} 皇冠` +
              `${e.capacity ? ` · ${CAPACITY_LABEL[e.capacity] ?? e.capacity}` : ''}` +
              `${e.stacked_on ? ` · 叠放在 ${e.stacked_on} 上` : ''}`}
          >
            <div className={`bought-mini-gem card-theme-${e.bonus ?? 'gray'}`} />
            <b>{e.points}</b>
            {(e.crowns ?? 0) > 0 && (
              <span className="bought-crowns">
                {Array.from({ length: e.crowns! }).map((_, i) => (
                  <CrownIcon key={i} size={9} />
                ))}
              </span>
            )}
            {e.capacity && <i className="bought-cap">{CAPACITY_LABEL[e.capacity] ?? e.capacity}</i>}
            {e.bonus_number > 1 && <i className="stacked-mark">×{e.bonus_number}</i>}
            {e.stacked_on && <i className="stacked-mark stacked-on">叠</i>}
          </span>
        ))}
        {player.royal_cards.map((r) => (
          <span key={r} className="bought-mini royal-mini" title="皇家牌">
            <b>皇</b>
          </span>
        ))}
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
