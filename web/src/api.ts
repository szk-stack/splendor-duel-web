/** REST 客户端：创建/加入房间。 */
import type { TokenColor } from './types'

export interface RoomResult {
  room_code: string
  token: string
  slot: number
}

// 子路径前缀：开发环境 BASE_URL='/'；生产构建时 --base=/splendir-duel/ 自动带上
export const BASE = import.meta.env.BASE_URL

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.message || `请求失败 (${res.status})`)
  }
  return data as T
}

export function createRoom(nickname: string): Promise<RoomResult> {
  return post<RoomResult>(`${BASE}api/rooms`, { nickname })
}

export function joinRoom(code: string, nickname: string): Promise<RoomResult> {
  return post<RoomResult>(`${BASE}api/rooms/${encodeURIComponent(code)}/join`, { nickname })
}

// 筹码展示辅助（前端通用）
export const TOKEN_LABEL: Record<TokenColor, string> = {
  white: '钻石',
  blue: '蓝宝石',
  green: '祖母绿',
  red: '红宝石',
  black: '黑曜石',
  pearl: '珍珠',
  gold: '金币',
}

export const CAPACITY_LABEL: Record<string, string> = {
  replay: '额外回合',
  take_on_board: '拿取指示物',
  take_priviledge: '拿取特权',
  steal_opponent_pawn: '偷取',
}
