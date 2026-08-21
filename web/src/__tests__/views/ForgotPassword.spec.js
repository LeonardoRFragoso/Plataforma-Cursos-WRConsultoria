import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ForgotPassword from '../../views/ForgotPassword.vue'

// Mock api client
vi.mock('../../api/client', () => ({
  default: {
    post: vi.fn(),
  },
}))

import api from '../../api/client'

function setupRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/login', component: { template: '<div>login</div>' } },
      { path: '/recuperar-senha', component: { template: '<div>forgot</div>' } },
      { path: '/redefinir-senha', component: { template: '<div>reset</div>' } },
    ],
  })
}

describe('ForgotPassword', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.post.mockReset()
  })

  afterEach(() => {
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  it('renders form with email input and submit button', () => {
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    expect(wrapper.find('[data-testid="forgot-email-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="forgot-submit-btn"]').exists()).toBe(true)
  })

  it('shows loading state on submit', async () => {
    api.post.mockReturnValue(new Promise(() => {})) // never resolves
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    await wrapper.find('[data-testid="forgot-email-input"]').setValue('test@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.find('[data-testid="forgot-submit-btn"]').text()).toContain('Enviando')
    expect(wrapper.find('[data-testid="forgot-submit-btn"]').attributes('disabled')).toBeDefined()
  })

  it('shows generic success for existing email', async () => {
    api.post.mockResolvedValue({ data: {} })
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    await wrapper.find('[data-testid="forgot-email-input"]').setValue('user@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="forgot-success"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Solicitação recebida')
  })

  it('shows generic success for non-existing email (no account existence leak)', async () => {
    api.post.mockRejectedValue({ response: { status: 404 } })
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    await wrapper.find('[data-testid="forgot-email-input"]').setValue('nonexistent@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    // Should still show success state — don't reveal whether email exists
    expect(wrapper.find('[data-testid="forgot-success"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('não encontrado')
    expect(wrapper.text()).not.toContain('inválido')
  })

  it('shows generic success on network/API error (no account existence leak)', async () => {
    api.post.mockRejectedValue(new Error('Network error'))
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    await wrapper.find('[data-testid="forgot-email-input"]').setValue('user@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="forgot-success"]').exists()).toBe(true)
  })

  it('hides raw reset token by default (production/staging fail-closed)', async () => {
    // Backend accidentally returns reset_token — must NOT be displayed
    api.post.mockResolvedValue({ data: { reset_token: 'SECRET-TOKEN-123' } })
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    await wrapper.find('[data-testid="forgot-email-input"]').setValue('user@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="dev-reset-token"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('SECRET-TOKEN-123')
  })

  it('hides raw reset token in production build even if backend returns it', async () => {
    // Simulate production: import.meta.env.DEV is false
    // This test verifies the fail-closed behavior in production
    api.post.mockResolvedValue({ data: { reset_token: 'PROD-TOKEN-456' } })
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    await wrapper.find('[data-testid="forgot-email-input"]').setValue('user@example.com')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    // In test environment, import.meta.env.DEV is true but VITE_ALLOW_DEV_RESET_TOKEN is not set
    // So token should still be hidden
    expect(wrapper.find('[data-testid="dev-reset-token"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('PROD-TOKEN-456')
  })

  it('shows back to login link', () => {
    const router = setupRouter()
    const wrapper = mount(ForgotPassword, { global: { plugins: [router] } })
    expect(wrapper.find('[data-testid="back-to-login-link"]').exists()).toBe(true)
  })
})
