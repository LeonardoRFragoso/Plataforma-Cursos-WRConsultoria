import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Toast from '../../components/Toast.vue'

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  const getToastEl = () => document.body.querySelector('[data-testid="toast"]')

  it('renders with message', () => {
    mount(Toast, {
      props: { message: 'Test message' },
    })
    expect(getToastEl().textContent).toContain('Test message')
  })

  it('applies success type class', () => {
    mount(Toast, {
      props: { message: 'Done', type: 'success' },
    })
    expect(getToastEl().className).toContain('bg-green-50')
  })

  it('applies error type class', () => {
    mount(Toast, {
      props: { message: 'Oops', type: 'error' },
    })
    expect(getToastEl().className).toContain('bg-red-50')
  })

  it('applies info type class', () => {
    mount(Toast, {
      props: { message: 'Hi', type: 'info' },
    })
    expect(getToastEl().className).toContain('bg-blue-50')
  })

  it('applies warning type class', () => {
    mount(Toast, {
      props: { message: 'Careful', type: 'warning' },
    })
    expect(getToastEl().className).toContain('bg-yellow-50')
  })

  it('displays title when provided', () => {
    mount(Toast, {
      props: { message: 'Body', title: 'Warning' },
    })
    expect(getToastEl().textContent).toContain('Warning')
  })

  it('emits dismiss on close button click', async () => {
    const wrapper = mount(Toast, {
      props: { message: 'Bye' },
    })
    const closeBtn = document.body.querySelector('button[aria-label="Fechar notificação"]')
    await closeBtn.click()
    expect(wrapper.emitted('dismiss')).toBeTruthy()
  })

  it('auto-dismisses after duration', () => {
    const wrapper = mount(Toast, {
      props: { message: 'Auto', duration: 1000 },
    })
    expect(wrapper.emitted('dismiss')).toBeFalsy()
    vi.advanceTimersByTime(1000)
    expect(wrapper.emitted('dismiss')).toBeTruthy()
  })

  it('does not auto-dismiss when duration is 0', () => {
    const wrapper = mount(Toast, {
      props: { message: 'Stay', duration: 0 },
    })
    vi.advanceTimersByTime(5000)
    expect(wrapper.emitted('dismiss')).toBeFalsy()
  })

  it('has role alert for accessibility', () => {
    mount(Toast, {
      props: { message: 'A11y' },
    })
    expect(getToastEl().getAttribute('role')).toBe('alert')
  })
})
