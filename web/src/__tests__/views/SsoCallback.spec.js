import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SsoCallback from '../../views/SsoCallback.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('../../layouts/AuthLayout.vue', () => ({
  default: {
    name: 'AuthLayout',
    template: '<div><slot /></div>',
  },
}))

import api from '../../api/client'

describe('SsoCallback Component', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/sso/callback', name: 'SsoCallback', component: SsoCallback },
        { path: '/login', component: { template: '<div>Login</div>' } },
        { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
      ],
    })
  })

  const mountWithQuery = async (query = {}) => {
    const queryStr = new URLSearchParams(query).toString()
    await router.push(`/sso/callback?${queryStr}`)
    await router.isReady()
    return mount(SsoCallback, { global: { plugins: [router] } })
  }

  it('shows loading state on mount', async () => {
    api.post.mockResolvedValueOnce({
      data: { access_token: 'tok', refresh_token: 'ref' },
    })
    api.get.mockResolvedValueOnce({ data: { role: 'admin' } })

    const wrapper = await mountWithQuery({ code: 'abc', state: 'xyz' })

    // Loading state should be visible before promises resolve
    expect(wrapper.find('[data-testid="sso-callback-loading-title"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Entrando na Plataforma de Cursos')
  })

  it('calls the exchange endpoint with code and state', async () => {
    api.post.mockResolvedValueOnce({
      data: { access_token: 'tok', refresh_token: 'ref' },
    })
    api.get.mockResolvedValueOnce({ data: { role: 'admin' } })

    await mountWithQuery({ code: 'mycode', state: 'mystate' })
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/api/v1/sso/exchange', {
      code: 'mycode',
      state: 'mystate',
    })
  })

  it('redirects to dashboard on success', async () => {
    api.post.mockResolvedValueOnce({
      data: { access_token: 'tok', refresh_token: 'ref' },
    })
    api.get.mockResolvedValueOnce({ data: { role: 'admin' } })

    await mountWithQuery({ code: 'abc', state: 'xyz' })
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('shows error on failure', async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Código expirado' } },
    })

    const wrapper = await mountWithQuery({ code: 'bad', state: 'xyz' })
    await flushPromises()

    expect(wrapper.find('[data-testid="sso-callback-error-title"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Código expirado')
  })

  it('shows error when code or state is missing', async () => {
    const wrapper = await mountWithQuery({})
    await flushPromises()

    expect(wrapper.find('[data-testid="sso-callback-error-title"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Parâmetros de autenticação ausentes')
  })

  it('navigates to login when retry button is clicked', async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Erro' } },
    })

    const wrapper = await mountWithQuery({ code: 'bad', state: 'xyz' })
    await flushPromises()

    await wrapper.find('[data-testid="sso-callback-retry"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')
  })
})
