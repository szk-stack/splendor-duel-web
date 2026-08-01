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
}

export function CardGrid({ tier, cards, deckSize, clickable, selectedId, onClick }: Props) {
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
      <div className="deck-info" title="牌库剩余">牌库 ×{deckSize}</div>
    </div>
  )
}
