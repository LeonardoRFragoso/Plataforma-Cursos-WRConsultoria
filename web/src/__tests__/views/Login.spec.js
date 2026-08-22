import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Login from '../../views/Login.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../../api/client'

describe('Login Component', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/login', name: 'Login', component: Login },
        { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
        { path: '/register', name: 'Register', component: { template: '<div>Register</div>' } },
        { path: '/recuperar-senha', component: { template: '<div>Forgot</div>' } },
        { path: '/redefinir-senha', component: { template: '<div>Reset</div>' } },
        { path: '/cursos/:id', component: { template: '<div>Curso</div>' } },
      ],
    })
  })

  it('renders login form', () => {
    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('has email and password inputs', () => {
    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    const emailInput = wrapper.find('input[type="text"]')
    const passwordInput = wrapper.find('input[type="password"]')

    expect(emailInput.exists()).toBe(true)
    expect(passwordInput.exists()).toBe(true)
  })

  it('has register link', () => {
    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    const registerLink = wrapper.find('[data-testid="login-register-link"]')
    expect(registerLink.exists()).toBe(true)
  })

  it('displays error message when provided', async () => {
    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    await wrapper.vm.$nextTick()
    wrapper.vm.error = 'Invalid credentials'
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Invalid credentials')
  })

  it('preserves redirect query in register link', async () => {
    await router.push('/login?redirect=/cursos/123')
    await router.isReady()

    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    const registerLink = wrapper.find('[data-testid="login-register-link"]')
    expect(registerLink.exists()).toBe(true)
    // The link should include the redirect query param
    expect(registerLink.attributes('href')).toContain('redirect')
    expect(registerLink.attributes('href')).toContain('cursos')
  })

  it('navigates to valid redirect after successful login', async () => {
    api.post.mockResolvedValueOnce({
      data: { access_token: 'tok', refresh_token: 'ref' },
    })
    api.get.mockResolvedValueOnce({ data: { role: 'student' } })

    await router.push('/login?redirect=/cursos/abc')
    await router.isReady()

    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    await wrapper.find('[data-testid="login-identifier"]').setValue('user@example.com')
    await wrapper.find('[data-testid="login-password"]').setValue('pass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/cursos/abc')
  })

  it('rejects malicious external redirect after login', async () => {
    api.post.mockResolvedValueOnce({
      data: { access_token: 'tok', refresh_token: 'ref' },
    })
    api.get.mockResolvedValueOnce({ data: { role: 'student' } })

    await router.push('/login?redirect=https://evil.example.com')
    await router.isReady()

    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    await wrapper.find('[data-testid="login-identifier"]').setValue('user@example.com')
    await wrapper.find('[data-testid="login-password"]').setValue('pass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    // Should fall back to student home (/dashboard), not external URL
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('uses default destination when no redirect provided', async () => {
    api.post.mockResolvedValueOnce({
      data: { access_token: 'tok', refresh_token: 'ref' },
    })
    api.get.mockResolvedValueOnce({ data: { role: 'student' } })

    await router.push('/login')
    await router.isReady()

    const wrapper = mount(Login, {
      global: { plugins: [router] },
    })

    await wrapper.find('[data-testid="login-identifier"]').setValue('user@example.com')
    await wrapper.find('[data-testid="login-password"]').setValue('pass123')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })
})
