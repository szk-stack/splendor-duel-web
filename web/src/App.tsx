import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { restoreSession, useGameStore } from './store'
import { HomePage } from './pages/Home'
import { LobbyPage } from './pages/Lobby'
import { GamePage } from './pages/Game'

// 模块加载时同步恢复会话（必须在首次渲染前，否则 Guard 会重定向回首页）
restoreSession()

function Guard({ children }: { children: React.ReactNode }) {
  const room = useGameStore((s) => s.room)
  if (!room) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/lobby" element={<Guard><LobbyPage /></Guard>} />
        <Route path="/game" element={<Guard><GamePage /></Guard>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  )
}
