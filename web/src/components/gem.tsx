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

/** 宝石 SVG 图标（六边形切面，纯矢量无版权） */
export function GemIcon({ color, size = 14 }: { color: TokenColor | 'joker' | null; size?: number }) {
  // 灰卡/百搭用中性色
  const fill = color === 'joker' ? '#f9d976' : color === null ? '#8a8f98' : `var(--gem-${color})`
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden>
      <polygon points="10,1 18,6 15,18 5,18 2,6" fill={fill} stroke="#ffffff88" strokeWidth="1" />
      <polygon points="10,1 10,9 2,6 18,6 10,9" fill="#ffffff55" />
      <polygon points="10,9 15,18 18,6 10,9" fill="#00000022" />
      <polygon points="10,9 5,18 2,6 10,9" fill="#00000033" />
    </svg>
  )
}

export function CrownIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 16" aria-hidden>
      <path
        d="M1 12 L2 4 L7 8 L10 2 L13 8 L18 4 L19 12 Z"
        fill="#f5c542"
        stroke="#b8860b"
        strokeWidth="1"
      />
      <rect x="1" y="13" width="18" height="2.5" rx="1" fill="#f5c542" stroke="#b8860b" strokeWidth="0.6" />
    </svg>
  )
}
