/** 首页：创建房间 / 加入房间。 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGameStore } from '../store'

export function HomePage() {
  const nav = useNavigate()
  const { create, join } = useGameStore()
  const sessionError = useGameStore((s) => s.error)
  const [nickname, setNickname] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const doAction = async (fn: () => Promise<void>) => {
    if (!nickname.trim() || busy) return
    setError(null)
    setBusy(true)
    try {
      await fn()
      nav('/lobby')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page home-page">
      <h1 className="home-title">💎 璀璨宝石：对决</h1>
      <p className="home-sub">双人在线对战 · 三种胜利之路</p>

      <div className="home-card">
        <label>
          昵称
          <input
            value={nickname}
            maxLength={16}
            placeholder="输入昵称（1-16 字）"
            onChange={(e) => setNickname(e.target.value)}
          />
        </label>

        <button
          className="action-btn action-btn-primary action-btn-wide"
          disabled={busy || !nickname.trim()}
          onClick={() => doAction(() => create(nickname))}
        >
          创建房间
        </button>

        <button
          className="action-btn action-btn-ai action-btn-wide"
          disabled={busy || !nickname.trim()}
          onClick={() => doAction(() => create(nickname, true))}
        >
          🤖 AI 对战（单人）
        </button>

        <div className="home-divider">或加入房间</div>

        <label>
          房间码
          <input
            value={code}
            maxLength={5}
            placeholder="5 位房间码"
            style={{ textTransform: 'uppercase' }}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
          />
        </label>
        <button
          className="action-btn action-btn-wide"
          disabled={busy || !nickname.trim() || code.trim().length !== 5}
          onClick={() => doAction(() => join(code.trim(), nickname))}
        >
          加入房间
        </button>

        {sessionError && <div className="banner banner-error">{sessionError}</div>}
        {error && <div className="banner banner-error">{error}</div>}
      </div>

      <details className="home-rules">
        <summary>📖 基本规则介绍（点击展开）</summary>
        <div className="home-rules-content">
          <h3>🎯 游戏目标</h3>
          <p>率先达成以下任一条件即获胜：</p>
          <ul>
            <li><b>声望 20 分</b>（所有卡牌分数合计）</li>
            <li><b>皇冠 10 个</b>（购买带皇冠的卡收集）</li>
            <li><b>同色 10 分</b>（同一种奖励色的卡牌分数合计，百搭卡按复制色计入）</li>
          </ul>

          <h3>🔁 回合结构</h3>
          <p>每回合：先可执行 <b>0~2 个可选行动</b>（按顺序：先特权、后补充棋盘），然后<b>必须执行 1 个强制行动</b>。</p>
          <ul>
            <li><b>使用特权</b>：放回 1~3 个特权，从棋盘拿取对应数量的宝石/珍珠（不能拿金币）</li>
            <li><b>补充棋盘</b>：从布袋补充空位；对手获得 1 个特权</li>
          </ul>

          <h3>⚡ 强制行动（三选一）</h3>
          <ul>
            <li><b>拿筹码</b>：拿取最多 3 个相邻的宝石/珍珠（横/竖/斜一条线，不能拿金币）；若拿 3 个同色或 2 个珍珠，对手获 1 特权</li>
            <li><b>保留牌</b>：拿 1 个金币，并从金字塔明牌或牌库顶保留 1 张牌（上限 3 张，唯一获得金币的方式）</li>
            <li><b>购买</b>：支付牌面费用（金币可充当任意宝石/珍珠）；购买的牌给予永久奖励色，抵扣未来购买费用</li>
          </ul>

          <h3>👑 皇冠与皇家牌</h3>
          <p>拥有 <b>3 个皇冠</b>时可拿取 1 张皇家牌，<b>6 个皇冠</b>时再拿 1 张（每人最多 2 张）。皇家牌提供分数和特殊能力（额外回合/拿特权/偷取）。</p>

          <h3>🌈 百搭卡</h3>
          <p>奖励色为百搭的卡购买时须<b>叠放到一张已有奖励的卡</b>上，复制其奖励色（百搭卡分数计入该色）。</p>

          <h3>📌 其他</h3>
          <ul>
            <li>回合结束时手牌超过 <b>10 个</b>必须弃到 10 个（放回布袋）</li>
            <li>开局后手获得 1 个特权；特权共 3 个，在玩家间流转</li>
            <li>卡牌能力：额外回合 / 拿取指示物 / 拿取特权 / 偷取对手筹码</li>
          </ul>
        </div>
      </details>
    </div>
  )
}
