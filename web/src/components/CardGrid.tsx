/** 金字塔一行（某一级的展示槽位）。 */
import type { CardData } from '../types'
import { CardView } from './Card'

interface Props {
  tier: number
  cards: (CardData | null)[]
  deckSize: number
  clickable?: (card: CardData) => boolean
  selectedId?: string | null
  onClick?: (card: CardData, tier: number, slot: number) => void
  deckClickable?: boolean
  onDeckClick?: (tier: number) => void
}

export function CardGrid({ tier, cards, deckSize, clickable, selectedId, onClick, deckClickable, onDeckClick }: Props) {
  return (
    <div className={`card-grid tier-${tier}`}>
      {cards.map((card, slot) =>
        card ? (
          <CardView
            key={card.id}
            card={card}
            selected={selectedId === card.id}
            highlight={clickable?.(card)}
            onClick={onClick && clickable?.(card) ? () => onClick(card, tier, slot) : undefined}
          />
        ) : (
          <div key={`empty-${slot}`} className="card card-empty" />
        ),
      )}
      <div
        className={['deck-info', deckClickable ? 'deck-info-clickable' : ''].filter(Boolean).join(' ')}
        title={deckClickable ? '点击从牌库顶盲保留一张' : '牌库剩余'}
        onClick={deckClickable && deckSize > 0 ? () => onDeckClick?.(tier) : undefined}
      >
        牌库 ×{deckSize}
      </div>
    </div>
  )
}
