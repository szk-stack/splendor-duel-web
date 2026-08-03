/** 行动模式切换：拿筹码 / 买牌 / 保留 / 特权 / 补充棋盘 + 确认取消。 */
import type { LegalAction } from '../types'

export type Mode = 'none' | 'take' | 'buy' | 'reserve' | 'privilege'

interface Props {
  mode: Mode
  legal: LegalAction[]
  busy: boolean
  selectionReady: boolean
  onMode: (m: Mode) => void
  onConfirm: () => void
  onCancel: () => void
  onFillBoard: () => void
}

export function ActionBar({ mode, legal, busy, selectionReady, onMode, onConfirm, onCancel, onFillBoard }: Props) {
  const kinds = legal.map((a) => a.kind)
  const hasTake = kinds.includes('take_tokens')
  const hasBuy = kinds.includes('buy')
  const hasReserve = kinds.includes('reserve')
  const hasPrivilege = kinds.includes('use_privilege')
  const hasFill = kinds.includes('fill_board')
  const forceFill = kinds.includes('force_fill')

  const btn = (active: boolean, disabled: boolean, label: string, onClick: () => void) => (
    <button
      className={['action-btn', active ? 'action-btn-active' : ''].join(' ')}
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  )

  return (
    <div className="action-bar">
      {forceFill && (
        <div className="force-fill-tip">
          当前无法执行任何行动，必须先「补充棋盘」：
          <button className="action-btn action-btn-primary" disabled={busy} onClick={onFillBoard}>
            补充棋盘
          </button>
        </div>
      )}
      {!forceFill && (
        <>
          {hasPrivilege && btn(mode === 'privilege', busy, '使用特权', () => onMode(mode === 'privilege' ? 'none' : 'privilege'))}
          {hasTake && btn(mode === 'take', busy, '拿宝石', () => onMode(mode === 'take' ? 'none' : 'take'))}
          {hasBuy && btn(mode === 'buy', busy, '购买', () => onMode(mode === 'buy' ? 'none' : 'buy'))}
          {hasReserve && btn(mode === 'reserve', busy, '保留', () => onMode(mode === 'reserve' ? 'none' : 'reserve'))}
          {hasFill && btn(false, busy, '补充棋盘', onFillBoard)}
          {mode !== 'none' && (
            <button className="action-btn action-btn-confirm" disabled={busy || !selectionReady} onClick={onConfirm}>
              确认
            </button>
          )}
          {mode !== 'none' && (
            <button className="action-btn" disabled={busy} onClick={onCancel}>
              取消
            </button>
          )}
        </>
      )}
    </div>
  )
}
