/** 游戏棋盘页：纯视图，只渲染服务端状态；选择器本地管理，提交后等服务端回执。 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGameStore } from '../store'
import type { Action, BuyOption, CardData, LegalAction } from '../types'
import { CAPACITY_LABEL } from '../api'
import { changeDiscard, toggleTakeCell } from '../gameLogic'
import { ChipArea } from '../components/ChipArea'
import { CardGrid } from '../components/CardGrid'
import { PlayerPanel } from '../components/PlayerPanel'
import { ActionBar, type Mode } from '../components/ActionBar'
import { PaymentPanel } from '../components/PaymentPanel'
import { DiscardPanel } from '../components/DiscardPanel'
import { Banner } from '../components/Banner'

export function GamePage() {
  const nav = useNavigate()
  const { room, gameState, legalActions, error, banner, sendAction, rematch, leave, reset, connStatus } = useGameStore()
  const [confirmExit, setConfirmExit] = useState(false)
  const [confirmConcede, setConfirmConcede] = useState(false)
  const [mode, setMode] = useState<Mode>('none')
  const [selCells, setSelCells] = useState<number[]>([])
  const [selCard, setSelCard] = useState<{ opt: BuyOption } | null>(null)
  const [pendingReserve, setPendingReserve] = useState<{
    source: 'pyramid' | 'deck'
    tier: number
    slot?: number
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [discardSel, setDiscardSel] = useState<Record<string, number>>({})

  // 每次服务端广播（新 gameState 对象）都复位 busy 与选择：
  // - 强制行动后回合/玩家变化
  // - 可选行动（特权/补充棋盘）后回合不变，但同样需要复位 busy
  // - 收到错误（行动被拒）时也要复位，避免界面卡死
  useEffect(() => {
    setMode('none')
    setSelCells([])
    setSelCard(null)
    setPendingReserve(null)
    setDiscardSel({})
    setBusy(false)
  }, [gameState, error])

  const me = gameState?.players.find((p) => p.slot === room?.slot)
  const opp = gameState?.players.find((p) => p.slot !== room?.slot)
  const myTurn = !!gameState && gameState.current === room?.slot

  const legal = useMemo(() => legalActions?.actions ?? [], [legalActions])
  const takeLegal = legal.find((a) => a.kind === 'take_tokens') as Extract<LegalAction, { kind: 'take_tokens' }> | undefined
  const buyLegal = legal.find((a) => a.kind === 'buy') as Extract<LegalAction, { kind: 'buy' }> | undefined
  const reserveLegal = legal.find((a) => a.kind === 'reserve') as Extract<LegalAction, { kind: 'reserve' }> | undefined
  const privilegeLegal = legal.find((a) => a.kind === 'use_privilege') as Extract<LegalAction, { kind: 'use_privilege' }> | undefined

  // ---------- 点击处理 ----------

  const changeDiscardColor = (color: string, delta: number) => {
    const held = me?.tokens[color as keyof typeof me.tokens] ?? 0
    setDiscardSel((prev) => changeDiscard(prev, color, delta, held))
  }

  const onCellClick = (cell: number) => {
    if (!myTurn || !gameState) return
    // 保留流程第二步：选择要拿的金币
    if (pendingReserve && reserveLegal && reserveLegal.gold_cells.includes(cell)) {
      sendAction({
        kind: 'reserve',
        source: pendingReserve.source,
        tier: pendingReserve.tier,
        ...(pendingReserve.slot !== undefined ? { slot: pendingReserve.slot } : {}),
        gold_cell: cell,
      })
      setPendingReserve(null)
      setMode('none')
      return
    }
    if (mode === 'privilege' && privilegeLegal) {
      sendAction({ kind: 'use_privilege', cell })
      setMode('none')
      return
    }
    if (mode === 'take' && takeLegal) {
      setSelCells((prev) => toggleTakeCell(prev, cell))
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
      // 进入保留流程：先选明牌，再选金币
      setPendingReserve({ source: 'pyramid', tier, slot })
    }
  }

  const onReservedClick = (card: CardData) => {
    if (!myTurn || mode !== 'buy' || !buyLegal) return
    const opt = buyLegal.options.find((o) => o.source === 'reserved' && o.card_id === card.id)
    if (opt) setSelCard({ opt })
  }

  const onDeckClick = (tier: number) => {
    if (!myTurn || !gameState || mode !== 'reserve' || !reserveLegal) return
    setPendingReserve({ source: 'deck', tier })
  }

  const buyablePyramid = (card: CardData) =>
    myTurn &&
    ((mode === 'buy' && !!buyLegal?.options.find(
      (o) => o.source === 'pyramid' && o.card.id === card.id,
    )) ||
      (mode === 'reserve' && !!reserveLegal))
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
    ? pendingReserve
      ? reserveLegal?.gold_cells ?? null
      : mode === 'take'
        ? takeLegal?.cells ?? null
        : mode === 'privilege'
          ? privilegeLegal?.cells ?? null
          : null
    : null

  // ---------- 渲染 ----------

  if (!gameState || !me || !opp) {
    const connecting = connStatus !== 'open'
    return (
      <div className="page">
        <div className="banner">
          {connecting ? (
            '正在连接对局…（刷新后自动重连）'
          ) : (
            <>
              对局尚未开始…（返回 <a onClick={() => { reset(); nav('/') }}>首页</a>）
            </>
          )}
        </div>
      </div>
    )
  }

  const exitRoom = () => {
    leave()  // 通知服务端释放席位（对局中对手获胜），稍后自动清理本地会话
    nav('/')
  }

  const concede = () => {
    sendAction({ kind: 'concede' })
    setConfirmConcede(false)
  }

  return (
    <div className="page game-page">
      <div className="game-toolbar">
        <span className="room-tag">房间 {room?.code}</span>
        <span className="toolbar-spacer" />
        {gameState.phase !== 'game_over' && (
          <button
            className={`action-btn ${confirmConcede ? 'action-btn-confirm' : ''}`}
            onClick={() => (confirmConcede ? concede() : setConfirmConcede(true))}
            onBlur={() => setConfirmConcede(false)}
          >
            {confirmConcede ? '确认认输？' : '认输'}
          </button>
        )}
        <button
          className={`action-btn ${confirmExit ? 'action-btn-confirm' : ''}`}
          onClick={() => (confirmExit ? exitRoom() : setConfirmExit(true))}
          onBlur={() => setConfirmExit(false)}
        >
          {confirmExit ? '确认退出？' : '退出'}
        </button>
      </div>

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
          <div className="royal-area">
            <div className="royal-title">皇家牌（拥有 3 个皇冠时取第 1 张，6 个皇冠时取第 2 张，每人最多 2 张）</div>
            <div className="royal-row">
              {gameState.royal_pool.map((r) => (
                <div key={r.id} className={`royal-mini-card ${r.capacity ? 'has-capacity' : ''}`}>
                  <b>{r.points}</b>
                  <span>分</span>
                  {r.capacity ? (
                    <i className="royal-cap">{CAPACITY_LABEL[r.capacity] ?? r.capacity}</i>
                  ) : (
                    <i className="royal-cap royal-cap-none">无能力</i>
                  )}
                </div>
              ))}
            </div>
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
              deckClickable={myTurn && mode === 'reserve' && !!reserveLegal}
              onDeckClick={onDeckClick}
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
            setPendingReserve(null)
          }}
          onFillBoard={() => {
            sendAction({ kind: 'fill_board' })
            setBusy(true)
          }}
        />
      )}

      {pendingReserve && (
        <div className="banner banner-turn">已选要保留的牌 — 请点击棋盘上的【金币】完成保留</div>
      )}

      {gameState.phase === 'discard' && myTurn && legalActions?.discard && (
        <DiscardPanel
          over={legalActions.discard.over}
          hand={me.tokens}
          selected={discardSel}
          onChange={changeDiscardColor}
          onConfirm={submitDiscard}
        />
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
              {gameState.win_reason === 'concede' &&
                (gameState.winner === me.slot ? '对手认输' : '你认输了')}
              {gameState.win_reason === 'forfeit' && '对手离开了，你获胜'}
            </p>
            {gameState.win_reason === 'forfeit' && (
              <p className="muted">房间还在，把房间码 {room?.code} 告诉朋友即可加入新对局</p>
            )}
            <div className="victory-actions">
              {gameState.win_reason !== 'forfeit' && (
                <button className="action-btn action-btn-confirm" onClick={rematch}>
                  再来一局
                </button>
              )}
              <button className="action-btn" onClick={exitRoom}>
                返回首页
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
