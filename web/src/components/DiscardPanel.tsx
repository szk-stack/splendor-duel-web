/** 弃牌面板：−/+ 步进选择要弃的筹码。 */
import type { TokenColor } from '../types'

interface Props {
  over: number
  hand: Record<TokenColor, number>
  selected: Record<string, number>
  onChange: (color: string, delta: number) => void
  onConfirm: () => void
}

export function DiscardPanel({ over, hand, selected, onChange, onConfirm }: Props) {
  const total = Object.values(selected).reduce((s, n) => s + n, 0)
  return (
    <div className="discard-panel">
      <h4>请弃掉 {over} 个筹码（已选 {total}）</h4>
      <div className="discard-chips">
        {(Object.entries(hand) as [string, number][]).map(([color, count]) =>
          count > 0 ? (
            <div key={color} className={`discard-chip chip chip-${color}`}>
              <button className="discard-step" onClick={() => onChange(color, -1)} aria-label={`减少${color}`}>−</button>
              <b>{count}</b>
              <i>{selected[color] ? `弃 ${selected[color]}` : ''}</i>
              <button className="discard-step" onClick={() => onChange(color, 1)} aria-label={`增加${color}`}>+</button>
            </div>
          ) : null,
        )}
      </div>
      <div className="discard-actions">
        <button className="action-btn action-btn-confirm" disabled={total !== over} onClick={onConfirm}>
          确认弃牌
        </button>
      </div>
    </div>
  )
}
