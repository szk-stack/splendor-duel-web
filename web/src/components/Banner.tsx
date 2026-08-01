/** 顶部横幅：轮次/错误/掉线提示/连接状态。 */
interface Props {
  error: string | null
  banner: string | null
  myTurn: boolean
  nickname: string
  phase: string
  connStatus?: string
  opponentThinking?: boolean
}

export function Banner({ error, banner, myTurn, nickname, phase, connStatus, opponentThinking }: Props) {
  const statusText =
    connStatus === 'connecting' ? '连接中…' : connStatus === 'closed' ? '连接中断，正在重连…' : ''
  const turnText = phase === 'optional'
    ? myTurn
      ? `${nickname} 的回合`
      : opponentThinking
        ? '🤖 AI 思考中…'
        : '等待对手行动…'
    : ''

  return (
    <div className="banner-area">
      {statusText && <div className="banner banner-conn">{statusText}</div>}
      {turnText && <div className="banner banner-turn">{turnText}</div>}
      {banner && <div className="banner banner-info">{banner}</div>}
      {error && <div className="banner banner-error">{error}</div>}
    </div>
  )
}
