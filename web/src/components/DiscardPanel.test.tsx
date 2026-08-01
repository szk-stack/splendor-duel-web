/** 弃牌面板交互测试（用户反馈的"只能加不能减"bug 回归测试）。 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DiscardPanel } from './DiscardPanel'
import type { TokenColor } from '../types'

const hand: Record<TokenColor, number> = {
  white: 4, blue: 0, green: 0, red: 3, black: 0, pearl: 0, gold: 1,
}

function setup(over = 3) {
  const onChange = vi.fn()
  const onConfirm = vi.fn()
  render(
    <DiscardPanel
      over={over}
      hand={hand}
      selected={{}}
      onChange={onChange}
      onConfirm={onConfirm}
    />,
  )
  return { onChange, onConfirm }
}

describe('DiscardPanel', () => {
  it('点 + 增加、点 − 减少（受控回调）', async () => {
    const user = userEvent.setup()
    const { onChange } = setup()
    await user.click(screen.getByLabelText('增加red'))
    expect(onChange).toHaveBeenCalledWith('red', 1)
    await user.click(screen.getByLabelText('减少red'))
    expect(onChange).toHaveBeenCalledWith('red', -1)
  })

  it('未选够数量时确认按钮禁用', () => {
    setup(3)
    expect(screen.getByRole('button', { name: '确认弃牌' })).toBeDisabled()
  })

  it('显示持有量（白色筹码格显示 4）', () => {
    setup()
    expect(document.querySelector('.chip-white b')).toHaveTextContent('4')
    expect(document.querySelector('.chip-gold b')).toHaveTextContent('1')
    // 持有为 0 的颜色不渲染
    expect(document.querySelector('.chip-blue')).toBeNull()
  })

  it('红色筹码格含 − / + 步进按钮', () => {
    setup()
    expect(screen.getByLabelText('增加red')).toBeInTheDocument()
    expect(screen.getByLabelText('减少red')).toBeInTheDocument()
  })
})
