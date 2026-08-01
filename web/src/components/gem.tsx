/** 宝石筹码与颜色的样式辅助。 */
import type { TokenColor } from '../types'

/** 筹码 CSS 类（颜色映射在 index.css 中） */
export function chipClass(color: TokenColor): string {
  return `chip chip-${color}`
}

/** 卡面主题渐变（按奖励色），灰卡/百搭卡单独处理 */
export function cardTheme(bonus: TokenColor | 'joker' | null): string {
  if (bonus === 'joker') return 'card-theme-joker'
  if (bonus === null) return 'card-theme-gray'
  return `card-theme-${bonus}`
}

/** 宝石 SVG 图标（六边形切面，纯矢量无版权）。dark: 浅底/多彩底上用深色描边 */
export function GemIcon({ color, size = 14, dark = false }: {
  color: TokenColor | 'joker' | null; size?: number; dark?: boolean
}) {
  // 百搭卡用金色渐变（= 游戏里的万能金币）；灰卡显示空轮廓，不在此处渲染
  const fill = color === 'joker' ? 'url(#joker-gem)' : color === null ? '#8a8f98' : `var(--gem-${color})`
  const stroke = dark ? '#1a1d2a88' : '#ffffff88'
  const sheen = dark ? '#1a1d2a22' : '#ffffff55'
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden>
      <defs>
        <linearGradient id="joker-gem" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#f8dd8f" />
          <stop offset="100%" stopColor="#c9962a" />
        </linearGradient>
      </defs>
      <polygon points="10,1 18,6 15,18 5,18 2,6" fill={fill} stroke={stroke} strokeWidth="1" />
      <polygon points="10,1 10,9 2,6 18,6 10,9" fill={sheen} />
      <polygon points="10,9 15,18 18,6 10,9" fill="#00000022" />
      <polygon points="10,9 5,18 2,6 10,9" fill="#00000033" />
    </svg>
  )
}

export function CrownIcon({ size = 14, outline = false }: { size?: number; outline?: boolean }) {
  // outline: 黑边版本，用于彩色卡面上（面板深色背景上用默认深金边）
  const stroke = outline ? '#000000' : '#b8860b'
  const sw = outline ? 1.5 : 1
  return (
    <svg width={size} height={size} viewBox="0 0 20 16" aria-hidden>
      <path
        d="M1 12 L2 4 L7 8 L10 2 L13 8 L18 4 L19 12 Z"
        fill="#f5c542"
        stroke={stroke}
        strokeWidth={sw}
      />
      <rect x="1" y="13" width="18" height="2.5" rx="1" fill="#f5c542" stroke={stroke} strokeWidth={sw * 0.6} />
    </svg>
  )
}
