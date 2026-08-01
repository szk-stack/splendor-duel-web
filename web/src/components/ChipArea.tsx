/** 5×5 宝石棋盘。 */
import type { GameState, TokenColor } from '../types'
import { chipClass } from './gem'

interface Props {
  gameState: GameState
  selectableCells: number[] | null   // 可点击的格位（take/privilege 模式）
  selectedCells: number[]
  onClick: (cell: number) => void
}

export function ChipArea({ gameState, selectableCells, selectedCells, onClick }: Props) {
  const cells = Array.from({ length: 25 }, (_, i) => ({
    i,
    color: gameState.board[i],
    selectable: selectableCells?.includes(i) ?? false,
    selected: selectedCells.includes(i),
  }))

  return (
    <div className="chip-area">
      {cells.map(({ i, color, selectable, selected }) => (
        <div
          key={i}
          className={[
            'board-cell',
            color ? '' : 'board-cell-empty',
            selectable ? 'board-cell-selectable' : '',
            selected ? 'board-cell-selected' : '',
          ].filter(Boolean).join(' ')}
          onClick={() => selectable && onClick(i)}
        >
          {color && <div className={chipClass(color as TokenColor)} />}
        </div>
      ))}
    </div>
  )
}
