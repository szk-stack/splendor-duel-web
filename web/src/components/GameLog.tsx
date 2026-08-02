/** 对局日志面板：底部可滚动窗口，记录双方每步操作（含卡面与能力效果）。 */
import { useEffect, useRef } from 'react'
import { useGameStore } from '../store'
import type { LogEntry } from '../types'
import { TOKEN_LABEL } from '../api'
import { CardView } from './Card'
import type { TokenColor } from '../types'

function colorSummary(tokens?: Record<string, number>): string {
  if (!tokens) return ''
  return Object.entries(tokens)
    .filter(([, n]) => n > 0)
    .map(([c, n]) => `${n}${TOKEN_LABEL[c as TokenColor] ?? c}`)
    .join('、')
}

function paymentSummary(payment?: Record<string, { tokens: number; gold: number }>): string {
  if (!payment) return ''
  const parts: string[] = []
  for (const [c, v] of Object.entries(payment)) {
    if (v.tokens) parts.push(`${v.tokens}${TOKEN_LABEL[c as TokenColor] ?? c}`)
    if (v.gold) parts.push(`${v.gold}金币`)
  }
  return parts.join('、') || '免费'
}

function renderEntry(e: LogEntry): React.ReactNode {
  const effects = e.effects?.length
    ? `（发动效果：${e.effects.join('；')}）`
    : ''
  switch (e.type) {
    case 'buy':
      return (
        <>
          {e.player} 花费了 {paymentSummary(e.payment)} 购买了 {e.card && <CardView card={e.card} />}
          {effects}
        </>
      )
    case 'take_tokens':
      return <>{e.player} 拿取了 {colorSummary(e.tokens)}</>
    case 'reserve':
      return (
        <>
          {e.player} 获取了1个金币，保留了 {e.card && <CardView card={e.card} />}
        </>
      )
    case 'fill_board':
      return <>{e.player} 补充了棋盘</>
    case 'use_privilege':
      return (
        <>
          {e.player} 使用 {e.privileges_used ?? 1} 个特权兑换了 {colorSummary(e.tokens)}
        </>
      )
    case 'royal':
      return (
        <>
          {e.player} 获得了第 {e.royal_index ?? 1} 张皇家卡：
          {e.royal_card && (
            <span className="log-royal-card" title={`${e.royal_card.points} 分${e.royal_card.capacity ? ` · ${e.royal_card.capacity}` : ''}`}>
              <b>{e.royal_card.points}分</b>
              {e.royal_card.capacity && <i>{e.royal_card.capacity}</i>}
            </span>
          )}
          {effects}
        </>
      )
    case 'discard':
      return <>{e.player} 弃掉了 {colorSummary(e.tokens)}</>
    case 'concede':
      return <>{e.player} 认输了</>
    default:
      return <>{e.player} 执行了 {e.type}</>
  }
}

export function GameLog() {
  const gameLog = useGameStore((s) => s.gameLog)
  const boxRef = useRef<HTMLDivElement>(null)

  // 新条目自动滚到底部
  useEffect(() => {
    const el = boxRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [gameLog.length])

  return (
    <div className="game-log">
      <div className="game-log-title">📜 对局日志</div>
      <div className="game-log-box" ref={boxRef}>
        {gameLog.length === 0 && <div className="game-log-empty">暂无操作记录</div>}
        {gameLog.map((e, i) => (
          <div key={i} className="game-log-entry">
            {renderEntry(e)}
          </div>
        ))}
      </div>
    </div>
  )
}
