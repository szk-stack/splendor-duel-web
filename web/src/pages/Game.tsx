/** 游戏棋盘页：纯视图，只渲染服务端状态；选择器本地管理，提交后等服务端回执。 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGameStore } from '../store'
import type { Action, BuyOption, CardData, LegalAction } from '../types'
import { ChipArea } from '../components/ChipArea'
import { CardGrid } from '../components/CardGrid'
import { PlayerPanel } from '../components/PlayerPanel'
import { ActionBar, type Mode } from '../components/ActionBar'
import { PaymentPanel } from '../components/PaymentPanel'
import { Banner } from '../components/Banner'

function inLine(cells: number[]): boolean {
  if (cells.length <= 1) return true
  const dir = (a: number, b: number) => [a % 5 - b % 5, Math.floor(a / 5) - Math.floor(b / 5)]
  const d = dir(cells[0], cells[1])
  for (let i = 1; i < cells.length - 1; i++) {
    const d2 = dir(cells[i], cells[i + 1])
    if (d[0] !== d2[0] || d[1] !== d2[1]) return false
  }
  return true
}

export function GamePage() {
  const nav = useNavigate()
  const { room, gameState, legalActions, error, banner, sendAction, reset } = useGameStore()
  const [mode, setMode] = useState<Mode>('none')
  const [selCells, setSelCells] = useState<number[]>([])
  const [selCard, setSelCard] = useState<{ opt: BuyOption } | null>(null)
  const [busy, setBusy] = useState(false)
  const [discardSel, setDiscardSel] = useState<Record<string, number>>({})

  // 新状态到达后清空所有选择（服务端状态是唯一真相）
  useEffect(() => {
    setMode('none')
    setSelCells([])
    setSelCard(null)
    setDiscardSel({})
    setBusy(false)
  }, [gameState?.turn, gameState?.current])

  const me = gameState?.players.find((p) => p.slot === room?.slot)
  const opp = gameState?.players.find((p) => p.slot !== room?.slot)
  const myTurn = !!gameState && gameState.current === room?.slot

  const legal = useMemo(() => legalActions?.actions ?? [], [legalActions])
  const takeLegal = legal.find((a) => a.kind === 'take_tokens') as Extract<LegalAction, { kind: 'take_tokens' }> | undefined
  const buyLegal = legal.find((a) => a.kind === 'buy') as Extract<LegalAction, { kind: 'buy' }> | undefined
  const reserveLegal = legal.find((a) => a.kind === 'reserve') as Extract<LegalAction, { kind: 'reserve' }> | undefined
  const privilegeLegal = legal.find((a) => a.kind === 'use_privilege') as Extract<LegalAction, { kind: 'use_privilege' }> | undefined

  // ---------- 点击处理 ----------

  const toggleDiscardColor = (color: string) => {
    setDiscardSel((prev) => {
      const next = { ...prev }
      const cur = next[color] ?? 0
      if (cur >= (me?.tokens[color as keyof typeof me.tokens] ?? 0)) return prev
      next[color] = cur + 1
      return next
    })
  }

  const onCellClick = (cell: number) => {
    if (!myTurn || !gameState) return
    if (mode === 'privilege' && privilegeLegal) {
      sendAction({ kind: 'use_privilege', cell })
      setMode('none')
      return
    }
    if (mode === 'take' && takeLegal) {
      setSelCells((prev) => {
        if (prev.includes(cell)) return prev.filter((c) => c !== cell)
        if (prev.length >= 3) return prev
        const next = [...prev, cell]
        return inLine(next) ? next : prev
      })
    }
  }

  const onCardClick = (_card: CardData, tier: number, slot: number) => {
    if (!myTurn || !gameState) return
    if (mode === 'buy' && buyLegal) {
      const opt = buyLegal.options.find(
        (o) => o.source === 'pyramid' && o.tier === tier && o.slot === slot,
      )
      if (opt) setSelCard({ opt })
    } else if (mode === 'reserve' && reserveLegal) {
      const goldCell = reserveLegal.gold_cells[0]
      if (goldCell === undefined) return
      sendAction({ kind: 'reserve', source: 'pyramid', tier, slot, gold_cell: goldCell })
      setMode('none')
    }
  }

  const onReservedClick = (card: CardData) => {
    if (!myTurn || mode !== 'buy' || !buyLegal) return
    const opt = buyLegal.options.find((o) => o.source === 'reserved' && o.card_id === card.id)
    if (opt) setSelCard({ opt })
  }

  const buyablePyramid = (card: CardData) =>
    myTurn && mode === 'buy' && !!buyLegal?.options.find(
      (o) => o.source === 'pyramid' && o.card.id === card.id,
    )
  const buyableReserved = (card: CardData) =>
    myTurn && mode === 'buy' && !!buyLegal?.options.find(
      (o) => o.source === 'reserved' && o.card_id === card.id,
    )

  // ---------- 提交 ----------

  const submitTake = () => {
    sendAction({ kind: 'take_tokens', cells: selCells })
    setBusy(true)
  }

  const submitBuy = (payload: Record<string, unknown>) => {
    if (!selCard) return
    const { opt } = selCard
    const action: Action = {
      kind: 'buy',
      source: opt.source,
      payment: payload.payment,
      ...(opt.tier !== undefined ? { tier: opt.tier } : {}),
      ...(opt.slot !== undefined ? { slot: opt.slot } : {}),
      ...(opt.card_id ? { card_id: opt.card_id } : {}),
      ...(payload.joker_target ? { joker_target: payload.joker_target } : {}),
      ...(payload.steal_color ? { steal_color: payload.steal_color } : {}),
      ...(payload.take_cell !== undefined ? { take_cell: payload.take_cell } : {}),
      ...(payload.royal_choice ? { royal_choice: payload.royal_choice } : {}),
    }
    sendAction(action)
    setSelCard(null)
    setMode('none')
    setBusy(true)
  }

  const submitDiscard = () => {
    if (!gameState) return
    const total = Object.values(discardSel).reduce((s, n) => s + n, 0)
    const over = legalActions?.discard?.over ?? 0
    if (total !== over) return
    sendAction({ kind: 'discard', colors: discardSel })
    setBusy(true)
  }

  const selectableCells = myTurn
    ? mode === 'take'
      ? takeLegal?.cells ?? null
      : mode === 'privilege'
        ? privilegeLegal?.cells ?? null
        : null
    : null

  // ---------- 渲染 ----------

  if (!gameState || !me || !opp) {
    return (
      <div className="page">
        <div className="banner">对局尚未开始…（返回 <a onClick={() => { reset(); nav('/') }}>首页</a>）</div>
      </div>
    )
  }

  return (
    <div className="page game-page">
      <Banner
        error={error}
        banner={banner}
        myTurn={myTurn}
        nickname={me.nickname}
        phase={gameState.phase}
      />

      <PlayerPanel
        player={opp}
        isMe={false}
        isCurrent={gameState.current === opp.slot}
        reservedClickable={buyableReserved}
        onReservedClick={onReservedClick}
      />

      <div className="board">
        {gameState.royal_pool.length > 0 && (
          <div className="royal-row">
            {gameState.royal_pool.map((r) => (
              <div key={r.id} className={`royal-mini-card ${r.capacity ? 'has-capacity' : ''}`}>
                <b>{r.points}</b>
                <span>分</span>
                {r.capacity && <i className="royal-cap">{r.capacity}</i>}
              </div>
            ))}
          </div>
        )}

        <ChipArea
          gameState={gameState}
          selectableCells={selectableCells}
          selectedCells={selCells}
          onClick={onCellClick}
        />

        <div className="pyramid">
          {[3, 2, 1].map((tier) => (
            <CardGrid
              key={tier}
              tier={tier}
              cards={gameState.pyramid[String(tier)]}
              deckSize={gameState.deck_sizes[String(tier)] ?? 0}
              clickable={buyablePyramid}
              selectedId={selCard?.opt.card.id}
              onClick={onCardClick}
            />
          ))}
        </div>
      </div>

      <PlayerPanel
        player={me}
        isMe
        isCurrent={myTurn}
        reservedClickable={buyableReserved}
        onReservedClick={onReservedClick}
      />

      {gameState.phase === 'optional' && myTurn && (
        <ActionBar
          mode={mode}
          legal={legal}
          busy={busy}
          selectionReady={
            (mode === 'take' && selCells.length > 0) ||
            (mode === 'buy' && selCard !== null) ||
            mode === 'none' ||
            false
          }
          onMode={setMode}
          onConfirm={mode === 'take' ? submitTake : () => setBusy(false)}
          onCancel={() => {
            setMode('none')
            setSelCells([])
            setSelCard(null)
          }}
          onFillBoard={() => {
            sendAction({ kind: 'fill_board' })
            setBusy(true)
          }}
        />
      )}

      {gameState.phase === 'discard' && myTurn && (
        <div className="discard-panel">
          <h4>
            请弃掉 {legalActions?.discard?.over ?? 0} 个筹码（已选{' '}
            {Object.values(discardSel).reduce((s, n) => s + n, 0)}）
          </h4>
          <div className="discard-chips">
            {(Object.entries(me.tokens) as [string, number][]).map(([color, count]) =>
              count > 0 ? (
                <button
                  key={color}
                  className={`discard-chip chip chip-${color}`}
                  onClick={() => toggleDiscardColor(color)}
                  title={`点击弃掉 1 个（持有 ${count}）`}
                >
                  {count} <i>−{(discardSel[color] ?? 0) > 0 ? discardSel[color] : ''}</i>
                </button>
              ) : null,
            )}
          </div>
          <div className="discard-actions">
            <button
              className="action-btn action-btn-confirm"
              disabled={
                Object.values(discardSel).reduce((s, n) => s + n, 0) !== (legalActions?.discard?.over ?? 0)
              }
              onClick={submitDiscard}
            >
              确认弃牌
            </button>
          </div>
        </div>
      )}

      {selCard && (
        <div className="modal-overlay" onClick={() => setSelCard(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <PaymentPanel
              card={selCard.opt.card}
              me={me}
              gameState={gameState}
              stackTargets={selCard.opt.stack_targets}
              royalRequired={!!(selCard.opt as BuyOption & { royal_required?: boolean }).royal_required}
              onConfirm={submitBuy}
              onCancel={() => setSelCard(null)}
            />
          </div>
        </div>
      )}

      {gameState.winner !== null && (
        <div className="modal-overlay">
          <div className="modal victory-modal">
            <h2>{gameState.winner === me.slot ? '🎉 你赢了！' : '😔 你输了'}</h2>
            <p>
              {gameState.win_reason === 'points' && '声望分达到 20 分'}
              {gameState.win_reason === 'crowns' && '收集到 10 个皇冠'}
              {gameState.win_reason?.startsWith('same_color') && '同色卡牌声望分达到 10 分'}
            </p>
            <button className="action-btn action-btn-confirm" onClick={() => { reset(); nav('/') }}>
              返回首页
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
