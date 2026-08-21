import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ResetPassword from '../../views/ResetPassword.vue'

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
      { path: '/redefinir-senha', component: { template: '<div>reset</div>' } },
    ],
  })
}

async function mountView(query = {}) {
  const router = setupRouter()
  await router.push({ path: '/redefinir-senha', query })
  await router.isReady()
  return mount(ResetPassword, { global: { plugins: [router] } })
}

describe('ResetPassword', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.post.mockReset()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders form with token, password, confirm inputs', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('[data-testid="reset-token-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reset-password-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reset-confirm-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reset-submit-btn"]').exists()).toBe(true)
  })

  it('pre-fills token from query param', async () => {
    const wrapper = await mountView({ token: 'QUERY-TOKEN' })
    expect(wrapper.find('[data-testid="reset-token-input"]').element.value).toBe('QUERY-TOKEN')
  })

  it('shows error on password mismatch', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-testid="reset-token-input"]').setValue('valid-token')
    await wrapper.find('[data-testid="reset-password-input"]').setValue('password123')
    await wrapper.find('[data-testid="reset-confirm-input"]').setValue('different456')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.find('[data-testid="reset-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('As senhas não coincidem')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('shows error for password below minimum length', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-testid="reset-token-input"]').setValue('valid-token')
    await wrapper.find('[data-testid="reset-password-input"]').setValue('12345')
    await wrapper.find('[data-testid="reset-confirm-input"]').setValue('12345')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.find('[data-testid="reset-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('mínimo 6 caracteres')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('shows success on valid reset', async () => {
    api.post.mockResolvedValue({ data: {} })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="reset-token-input"]').setValue('valid-token')
    await wrapper.find('[data-testid="reset-password-input"]').setValue('newpass123')
    await wrapper.find('[data-testid="reset-confirm-input"]').setValue('newpass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="reset-success"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Senha redefinida')
  })

  it('shows error for invalid or expired token (400)', async () => {
    api.post.mockRejectedValue({ response: { status: 400 } })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="reset-token-input"]').setValue('expired-token')
    await wrapper.find('[data-testid="reset-password-input"]').setValue('newpass123')
    await wrapper.find('[data-testid="reset-confirm-input"]').setValue('newpass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="reset-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Token inválido ou expirado')
  })

  it('shows network error on connection failure', async () => {
    api.post.mockRejectedValue(new Error('Network error'))
    const wrapper = await mountView()
    await wrapper.find('[data-testid="reset-token-input"]').setValue('some-token')
    await wrapper.find('[data-testid="reset-password-input"]').setValue('newpass123')
    await wrapper.find('[data-testid="reset-confirm-input"]').setValue('newpass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="reset-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Não foi possível conectar')
  })

  it('shows login CTA on success', async () => {
    api.post.mockResolvedValue({ data: {} })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="reset-token-input"]').setValue('valid-token')
    await wrapper.find('[data-testid="reset-password-input"]').setValue('newpass123')
    await wrapper.find('[data-testid="reset-confirm-input"]').setValue('newpass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="reset-go-login"]').exists()).toBe(true)
  })

  it('shows loading state during submission', async () => {
    api.post.mockReturnValue(new Promise(() => {})) // never resolves
    const wrapper = await mountView()
    await wrapper.find('[data-testid="reset-token-input"]').setValue('valid-token')
    await wrapper.find('[data-testid="reset-password-input"]').setValue('newpass123')
    await wrapper.find('[data-testid="reset-confirm-input"]').setValue('newpass123')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.find('[data-testid="reset-submit-btn"]').text()).toContain('Redefinindo')
    expect(wrapper.find('[data-testid="reset-submit-btn"]').attributes('disabled')).toBeDefined()
  })
})
