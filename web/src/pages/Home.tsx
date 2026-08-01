/** 首页：创建房间 / 加入房间。 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGameStore } from '../store'

export function HomePage() {
  const nav = useNavigate()
  const { create, join } = useGameStore()
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

        {error && <div className="banner banner-error">{error}</div>}
      </div>
    </div>
  )
}
