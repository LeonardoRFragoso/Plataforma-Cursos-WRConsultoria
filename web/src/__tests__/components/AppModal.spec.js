import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import AppModal from '../../components/AppModal.vue'

describe('AppModal', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  const mountModal = (props = {}, slots = {}) => {
    return mount(AppModal, {
      props: { title: 'Test', ...props },
      slots,
    })
  }

  it('renders when modelValue is true', async () => {
    mountModal({ modelValue: true })
    await flushPromises()
    const overlay = document.body.querySelector('[role="dialog"]')
    expect(overlay).toBeTruthy()
    expect(overlay.style.display).not.toBe('none')
  })

  it('does not render when modelValue is false', async () => {
    mountModal({ modelValue: false })
    await flushPromises()
    const overlay = document.body.querySelector('[role="dialog"]')
    expect(overlay).toBeNull()
  })

  it('displays title', async () => {
    mountModal({ modelValue: true, title: 'My Modal Title' })
    await flushPromises()
    const titleEl = document.body.querySelector('h2')
    expect(titleEl.textContent).toContain('My Modal Title')
  })

  it('emits update:modelValue false on close button click', async () => {
    const wrapper = mountModal({ modelValue: true })
    await flushPromises()
    const closeBtn = document.body.querySelector('[data-testid="modal-close"]')
    expect(closeBtn).toBeTruthy()
    closeBtn.click()
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
  })

  it('emits close event on close button click', async () => {
    const wrapper = mountModal({ modelValue: true })
    await flushPromises()
    const closeBtn = document.body.querySelector('[data-testid="modal-close"]')
    closeBtn.click()
    await flushPromises()
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits update:modelValue false on backdrop click', async () => {
    const wrapper = mountModal({ modelValue: true })
    await flushPromises()
    const backdrop = document.body.querySelector('[data-testid="modal-backdrop"]')
    expect(backdrop).toBeTruthy()
    backdrop.click()
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
  })

  it('does not close on backdrop when closeOnBackdrop is false', async () => {
    const wrapper = mountModal({ modelValue: true, closeOnBackdrop: false })
    await flushPromises()
    const backdrop = document.body.querySelector('[data-testid="modal-backdrop"]')
    backdrop.click()
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeFalsy()
    expect(wrapper.emitted('close')).toBeFalsy()
  })

  it('closes on Escape key', async () => {
    const wrapper = mountModal({ modelValue: true })
    await flushPromises()
    const overlay = document.body.querySelector('[role="dialog"]')
    overlay.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([false])
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('does not close on Escape when closable is false', async () => {
    const wrapper = mountModal({ modelValue: true, closable: false })
    await flushPromises()
    const overlay = document.body.querySelector('[role="dialog"]')
    overlay.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeFalsy()
    expect(wrapper.emitted('close')).toBeFalsy()
  })

  it('renders footer slot content', async () => {
    mountModal({ modelValue: true }, { footer: () => 'Footer Content' })
    await flushPromises()
    expect(document.body.textContent).toContain('Footer Content')
  })

  it('focuses dialog container on open', async () => {
    // With closable=false, the dialog container (dialogRef) receives focus.
    // The focus watch is not immediate, so we open the modal by toggling modelValue.
    const wrapper = mountModal({ modelValue: false, closable: false })
    await flushPromises()
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    await nextTick()
    const dialog = document.body.querySelector('[role="document"]')
    expect(dialog).toBeTruthy()
    expect(document.activeElement).toBe(dialog)
  })

  it('applies size class', async () => {
    mountModal({ modelValue: true, size: 'sm' })
    await flushPromises()
    let dialog = document.body.querySelector('[role="document"]')
    expect(dialog.className).toContain('max-w-md')

    document.body.innerHTML = ''

    mountModal({ modelValue: true, size: 'lg' })
    await flushPromises()
    dialog = document.body.querySelector('[role="document"]')
    expect(dialog.className).toContain('max-w-2xl')
  })
})
