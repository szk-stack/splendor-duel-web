/** 等待大厅：显示房间码，对手加入后自动开局进入棋盘。 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGameStore } from '../store'

export function LobbyPage() {
  const nav = useNavigate()
  const { room, nickname, gameState, connStatus, leave } = useGameStore()
  const [copied, setCopied] = useState(false)

  // 开局后自动进入棋盘
  useEffect(() => {
    if (gameState) nav('/game')
  }, [gameState, nav])

  if (!room) {
    return (
      <div className="page">
        <div className="banner">
          未加入房间，<a onClick={() => nav('/')}>返回首页</a>
        </div>
      </div>
    )
  }

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(room.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* 剪贴板不可用时忽略 */
    }
  }

  return (
    <div className="page lobby-page">
      <h1 className="home-title">房间已创建</h1>
      <p className="lobby-tip">把房间码告诉朋友，让 TA 在首页输入加入</p>

      <div className="room-code" onClick={copyCode} title="点击复制">
        {room.code}
      </div>
      <button className="action-btn" onClick={copyCode}>
        {copied ? '✅ 已复制' : '复制房间码'}
      </button>

      <div className="lobby-status">
        {connStatus === 'connecting' || connStatus === 'closed' ? (
          <span>连接中…</span>
        ) : (
          <span>等待对手加入（{nickname} 已就位）…</span>
        )}
      </div>

      <button className="action-btn lobby-leave" onClick={() => { leave(); nav('/') }}>
        离开房间
      </button>
    </div>
  )
}
