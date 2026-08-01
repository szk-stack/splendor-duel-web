/** WebSocket 客户端：连接/心跳/指数退避重连/事件分发。 */
import type { ClientMessage, ServerMessage } from './types'

const HEARTBEAT_INTERVAL = 25_000
const MAX_BACKOFF = 30_000

export type WsStatus = 'connecting' | 'open' | 'closed'

export class WsClient {
  status: WsStatus = 'closed'
  private ws: WebSocket | null = null
  private handlers: { [type: string]: ((msg: any) => void)[] } = {}
  private backoff = 1000
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private closedByUser = false
  private code = ''
  private token = ''

  connect(code: string, token: string) {
    this.code = code
    this.token = token
    this.closedByUser = false
    this.open()
  }

  close() {
    this.closedByUser = true
    this.stopTimers()
    this.ws?.close()
    this.status = 'closed'
  }

  on<T extends ServerMessage['type']>(type: T, handler: (msg: Extract<ServerMessage, { type: T }>) => void) {
    ;(this.handlers[type] ??= []).push(handler as (msg: any) => void)
  }

  send(msg: ClientMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  private open() {
    this.status = 'connecting'
    const proto = location.protocol === 'https:' ? 'wss://' : 'ws://'
    // BASE_URL 前缀：开发环境 '/'；生产子路径部署如 /splendir-duel/
    const url = `${proto}${location.host}${import.meta.env.BASE_URL}ws?room=${encodeURIComponent(this.code)}&token=${encodeURIComponent(this.token)}`
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      this.status = 'open'
      this.backoff = 1000
      this.emit({ type: 'open' } as never)
      // 心跳
      this.heartbeatTimer = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) this.send({ type: 'ping' })
      }, HEARTBEAT_INTERVAL)
      // 页面恢复可见时立即探测连接
      document.addEventListener('visibilitychange', this.onVisibility)
    }

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as ServerMessage
        this.emit(msg)
      } catch {
        /* 忽略坏帧 */
      }
    }

    ws.onclose = (ev) => {
      this.stopTimers()
      this.status = 'closed'
      this.emit({ type: 'close' } as never)
      // 4001 = 认证失败（房间不存在/已失效/后端重启）：
      // 重试没有意义，停止重连并通知上层清理会话
      if (ev.code === 4001) {
        this.closedByUser = true
        this.emit({ type: 'auth_failed' } as never)
        return
      }
      if (!this.closedByUser) this.scheduleReconnect()
    }

    ws.onerror = () => {
      ws.close()
    }
  }

  private onVisibility = () => {
    if (!document.hidden) this.send({ type: 'ping' })
  }

  private scheduleReconnect() {
    if (this.retryTimer || this.closedByUser) return
    const delay = this.backoff
    this.backoff = Math.min(this.backoff * 2, MAX_BACKOFF)
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      this.open()
    }, delay)
  }

  private stopTimers() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer)
    this.heartbeatTimer = null
    if (this.retryTimer) clearTimeout(this.retryTimer)
    this.retryTimer = null
    document.removeEventListener('visibilitychange', this.onVisibility)
  }

  private emit(msg: any) {
    const list = this.handlers[msg?.type]
    if (list) for (const h of list) h(msg)
  }
}
