import { useEffect } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { restoreSession, useGameStore } from './store'
import { HomePage } from './pages/Home'
import { LobbyPage } from './pages/Lobby'
import { GamePage } from './pages/Game'

function Guard({ children }: { children: React.ReactNode }) {
  const room = useGameStore((s) => s.room)
  if (!room) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  useEffect(() => {
    restoreSession()
  }, [])

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
