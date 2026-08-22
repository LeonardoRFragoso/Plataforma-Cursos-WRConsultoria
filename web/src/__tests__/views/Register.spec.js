import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Register from '../../views/Register.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../../api/client'

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/register', name: 'Register', component: Register },
      { path: '/login', name: 'Login', component: { template: '<div>login</div>' } },
      { path: '/dashboard', component: { template: '<div>dashboard</div>' } },
      { path: '/cursos/:id', component: { template: '<div>curso</div>' } },
    ],
  })
}

describe('Register Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders registration form', () => {
    const router = buildRouter()
    const wrapper = mount(Register, { global: { plugins: [router] } })

    expect(wrapper.find('[data-testid="register-fullname"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="register-email"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="register-cpf"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="register-password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('preserves redirect query in login link', async () => {
    const router = buildRouter()
    await router.push('/register?redirect=/cursos/42')
    await router.isReady()

    const wrapper = mount(Register, { global: { plugins: [router] } })

    const loginLink = wrapper.find('[data-testid="register-login-link"]')
    expect(loginLink.exists()).toBe(true)
    expect(loginLink.attributes('href')).toContain('redirect')
    expect(loginLink.attributes('href')).toContain('cursos')
  })

  it('performs auto-login and returns to course after successful registration', async () => {
    // register call succeeds
    api.post.mockResolvedValueOnce({ data: {} })
    // login call succeeds (access_token + refresh_token)
    api.post.mockResolvedValueOnce({
      data: { access_token: 'tok', refresh_token: 'ref' },
    })
    // /auth/me call succeeds
    api.get.mockResolvedValueOnce({ data: { role: 'student' } })

    const router = buildRouter()
    await router.push('/register?redirect=/cursos/abc')
    await router.isReady()

    const wrapper = mount(Register, { global: { plugins: [router] } })

    await wrapper.find('[data-testid="register-fullname"]').setValue('Test User')
    await wrapper.find('[data-testid="register-email"]').setValue('new@example.com')
    await wrapper.find('[data-testid="register-cpf"]').setValue('52998224725')
    await wrapper.find('[data-testid="register-password"]').setValue('pass123')
    await wrapper.find('[data-testid="register-confirm"]').setValue('pass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    // Should have navigated to the course, not to /login
    expect(router.currentRoute.value.fullPath).toBe('/cursos/abc')
  })

  it('uses default destination when no redirect provided', async () => {
    api.post.mockResolvedValueOnce({ data: {} })
    api.post.mockResolvedValueOnce({ data: { access_token: 'tok', refresh_token: 'ref' } })
    api.get.mockResolvedValueOnce({ data: { role: 'student' } })

    const router = buildRouter()
    await router.push('/register')
    await router.isReady()

    const wrapper = mount(Register, { global: { plugins: [router] } })

    await wrapper.find('[data-testid="register-fullname"]').setValue('Test User')
    await wrapper.find('[data-testid="register-email"]').setValue('new@example.com')
    await wrapper.find('[data-testid="register-cpf"]').setValue('52998224725')
    await wrapper.find('[data-testid="register-password"]').setValue('pass123')
    await wrapper.find('[data-testid="register-confirm"]').setValue('pass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('leaves recoverable manual login path when auto-login fails', async () => {
    // register succeeds
    api.post.mockResolvedValueOnce({ data: {} })
    // auto-login fails
    api.post.mockRejectedValueOnce(new Error('Login failed'))

    const router = buildRouter()
    await router.push('/register?redirect=/cursos/xyz')
    await router.isReady()

    const wrapper = mount(Register, { global: { plugins: [router] } })

    await wrapper.find('[data-testid="register-fullname"]').setValue('Test User')
    await wrapper.find('[data-testid="register-email"]').setValue('new@example.com')
    await wrapper.find('[data-testid="register-cpf"]').setValue('52998224725')
    await wrapper.find('[data-testid="register-password"]').setValue('pass123')
    await wrapper.find('[data-testid="register-confirm"]').setValue('pass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    // Should show success message (account created) and manual login link
    expect(wrapper.find('[data-testid="register-success"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="register-manual-login-link"]').exists()).toBe(true)
    // Should NOT have navigated away
    expect(router.currentRoute.value.path).toBe('/register')
  })

  it('shows error when registration fails', async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Email already registered' } },
    })

    const router = buildRouter()
    await router.push('/register')
    await router.isReady()

    const wrapper = mount(Register, { global: { plugins: [router] } })

    await wrapper.find('[data-testid="register-fullname"]').setValue('Test User')
    await wrapper.find('[data-testid="register-email"]').setValue('dup@example.com')
    await wrapper.find('[data-testid="register-cpf"]').setValue('52998224725')
    await wrapper.find('[data-testid="register-password"]').setValue('pass123')
    await wrapper.find('[data-testid="register-confirm"]').setValue('pass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-testid="register-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Email already registered')
  })

  it('rejects mismatched passwords before submission', async () => {
    const router = buildRouter()
    await router.push('/register')
    await router.isReady()

    const wrapper = mount(Register, { global: { plugins: [router] } })

    await wrapper.find('[data-testid="register-fullname"]').setValue('Test User')
    await wrapper.find('[data-testid="register-email"]').setValue('new@example.com')
    await wrapper.find('[data-testid="register-cpf"]').setValue('52998224725')
    await wrapper.find('[data-testid="register-password"]').setValue('pass123')
    await wrapper.find('[data-testid="register-confirm"]').setValue('different')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-testid="register-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('As senhas não coincidem')
    // Should NOT have called the API
    expect(api.post).not.toHaveBeenCalled()
  })
})
