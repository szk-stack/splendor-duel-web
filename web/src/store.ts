/** 全局状态：房间信息、对局状态、连接状态。客户端零规则逻辑，只渲染服务端状态。 */
import { create } from 'zustand'
import { createRoom, joinRoom } from './api'
import { WsClient } from './ws'
import type { Action, GameState, LegalActions } from './types'

export const wsClient = new WsClient()

interface RoomInfo {
  code: string
  token: string
  slot: number
  ai?: boolean
}

interface GameStore {
  room: RoomInfo | null
  nickname: string
  connStatus: string
  gameState: GameState | null
  legalActions: LegalActions | null
  lastEvents: unknown[]
  error: string | null
  banner: string | null
  create: (nickname: string, ai?: boolean) => Promise<void>
  join: (code: string, nickname: string) => Promise<void>
  sendAction: (action: Action) => void
  rematch: () => void
  /** 退出房间：通知服务端释放席位后清理本地会话 */
  leave: () => void
  clearError: () => void
  reset: () => void
}

wsClient.on('state' as never, (msg: any) => {
  useGameStore.setState({
    gameState: msg.state,
    legalActions: msg.legal_actions,
    lastEvents: msg.events,
    error: null,
  })
})
wsClient.on('error' as never, (msg: any) => useGameStore.setState({ error: msg.message }))
wsClient.on('player_left' as never, () => useGameStore.setState({ banner: '对手掉线，等待重连…' }))
wsClient.on('opponent_reconnected' as never, () => useGameStore.setState({ banner: '对手已重连' }))
wsClient.on('open' as never, () => useGameStore.setState({ connStatus: 'open', banner: null }))
wsClient.on('close' as never, () => useGameStore.setState({ connStatus: 'closed' }))
// 认证失败（房间不存在/已失效/后端重启）：清掉僵尸会话，Guard 会自动跳回首页
wsClient.on('auth_failed' as never, () => {
  sessionStorage.removeItem('splendor_room')
  sessionStorage.removeItem('splendor_nickname')
  useGameStore.setState({
    room: null,
    gameState: null,
    legalActions: null,
    lastEvents: [],
    connStatus: 'closed',
    banner: null,
    error: '房间不存在或已失效，请重新创建/加入房间',
  })
})

export const useGameStore = create<GameStore>((set) => ({
  room: null,
  nickname: '',
  connStatus: 'closed',
  gameState: null,
  legalActions: null,
  lastEvents: [],
  error: null,
  banner: null,

  create: async (nickname, ai = false) => {
    const r = await createRoom(nickname, ai)
    const room = { code: r.room_code, token: r.token, slot: r.slot, ai }
    // 清掉上一局的残留状态，避免新房间误显示旧对局
    set({ room, nickname, connStatus: 'connecting', gameState: null, legalActions: null,
          lastEvents: [], error: null, banner: null })
    sessionStorage.setItem('splendor_room', JSON.stringify(room))
    sessionStorage.setItem('splendor_nickname', nickname)
    wsClient.connect(room.code, room.token)
  },

  join: async (code, nickname) => {
    const r = await joinRoom(code, nickname)
    const room = { code: r.room_code, token: r.token, slot: r.slot }
    set({ room, nickname, connStatus: 'connecting', gameState: null, legalActions: null,
          lastEvents: [], error: null, banner: null })
    sessionStorage.setItem('splendor_room', JSON.stringify(room))
    sessionStorage.setItem('splendor_nickname', nickname)
    wsClient.connect(room.code, room.token)
  },

  sendAction: (action) => {
    wsClient.send({ type: 'action', action })
  },

  rematch: () => {
    wsClient.send({ type: 'rematch' })
  },

  leave: () => {
    wsClient.send({ type: 'leave' })
    // 等服务端处理完再断开（消息是异步发送的），同时清空本地对局状态
    setTimeout(() => {
      wsClient.close()
      sessionStorage.removeItem('splendor_room')
      sessionStorage.removeItem('splendor_nickname')
      set({ room: null, gameState: null, legalActions: null, lastEvents: [],
            error: null, banner: null })
    }, 300)
  },

  clearError: () => set({ error: null }),
  reset: () => {
    wsClient.close()
    sessionStorage.removeItem('splendor_room')
    sessionStorage.removeItem('splendor_nickname')
    set({ room: null, gameState: null, legalActions: null, error: null, banner: null })
  },
}))

/** 恢复 sessionStorage 中的房间（刷新页面后重连） */
export function restoreSession() {
  const raw = sessionStorage.getItem('splendor_room')
  const nickname = sessionStorage.getItem('splendor_nickname') ?? ''
  const { room, connStatus } = useGameStore.getState()
  if (raw && !room) {
    try {
      const r = JSON.parse(raw) as RoomInfo
      useGameStore.setState({ room: r, nickname })
    } catch {
      sessionStorage.removeItem('splendor_room')
      return
    }
  }
  const current = useGameStore.getState()
  if (current.room && connStatus === 'closed') {
    wsClient.connect(current.room.code, current.room.token)
  }
}
