import { describe, it, expect, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ConfirmDialog from '../../components/ConfirmDialog.vue'

describe('ConfirmDialog', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  const mountDialog = (props = {}, attrs = {}) => {
    return mount(ConfirmDialog, {
      props: { title: 'Test', message: 'Are you sure?', ...props },
      attrs,
    })
  }

  it('renders when modelValue is true', async () => {
    mountDialog({ modelValue: true })
    await flushPromises()
    const overlay = document.body.querySelector('[role="dialog"]')
    expect(overlay).toBeTruthy()
  })

  it('displays title and message', async () => {
    mountDialog({ modelValue: true, title: 'Confirm Action', message: 'Are you sure?' })
    await flushPromises()
    expect(document.body.textContent).toContain('Confirm Action')
    expect(document.body.textContent).toContain('Are you sure?')
  })

  it('emits confirm on confirm button click', async () => {
    const wrapper = mountDialog({ modelValue: true })
    await flushPromises()
    const confirmBtn = document.body.querySelector('[data-testid="confirm-ok"]')
    expect(confirmBtn).toBeTruthy()
    confirmBtn.click()
    await flushPromises()
    expect(wrapper.emitted('confirm')).toBeTruthy()
  })

  it('emits cancel and closes on cancel button click', async () => {
    const wrapper = mountDialog({ modelValue: true })
    await flushPromises()
    const cancelBtn = document.body.querySelector('[data-testid="confirm-cancel"]')
    expect(cancelBtn).toBeTruthy()
    cancelBtn.click()
    await flushPromises()
    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
  })

  it('disables both buttons when loading', async () => {
    mountDialog({ modelValue: true, loading: true })
    await flushPromises()
    const confirmBtn = document.body.querySelector('[data-testid="confirm-ok"]')
    const cancelBtn = document.body.querySelector('[data-testid="confirm-cancel"]')
    expect(confirmBtn.hasAttribute('disabled')).toBe(true)
    expect(cancelBtn.hasAttribute('disabled')).toBe(true)
  })

  it('shows loading text on confirm button when loading', async () => {
    mountDialog({ modelValue: true, loading: true })
    await flushPromises()
    const confirmBtn = document.body.querySelector('[data-testid="confirm-ok"]')
    expect(confirmBtn.textContent).toContain('Processando...')
  })

  it('applies danger class to confirm button', async () => {
    mountDialog({ modelValue: true, danger: true })
    await flushPromises()
    const confirmBtn = document.body.querySelector('[data-testid="confirm-ok"]')
    expect(confirmBtn.className).toContain('bg-red-600')
  })

  it('uses custom confirm and cancel text', async () => {
    mountDialog({ modelValue: true, confirmText: 'Delete', cancelText: 'Abort' })
    await flushPromises()
    const confirmBtn = document.body.querySelector('[data-testid="confirm-ok"]')
    const cancelBtn = document.body.querySelector('[data-testid="confirm-cancel"]')
    expect(confirmBtn.textContent).toContain('Delete')
    expect(cancelBtn.textContent).toContain('Abort')
  })

  it('forwards data-testid attribute to content div', async () => {
    mountDialog({ modelValue: true }, { 'data-testid': 'my-confirm-dialog' })
    await flushPromises()
    const content = document.body.querySelector('[data-testid="confirm-dialog-content"]')
    expect(content).toBeTruthy()
  })

  it('cancel does nothing when loading', async () => {
    const wrapper = mountDialog({ modelValue: true, loading: true })
    await flushPromises()
    const cancelBtn = document.body.querySelector('[data-testid="confirm-cancel"]')
    cancelBtn.click()
    await flushPromises()
    expect(wrapper.emitted('cancel')).toBeFalsy()
  })
})
