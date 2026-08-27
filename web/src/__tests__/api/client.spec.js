import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import api from '../../api/client'

const originalAdapter = api.defaults.adapter

const makeResponse = (config, data = {}) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
})

describe('API Client', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    api.defaults.adapter = originalAdapter
  })

  it('adds Authorization header when a token exists', () => {
    const authStore = useAuthStore()
    authStore.token = 'abc'

    const requestInterceptor = api.interceptors.request.handlers[0].fulfilled
    const config = requestInterceptor({ headers: {} })

    expect(config.headers.Authorization).toBe('Bearer abc')
  })

  it('does not add Authorization header when there is no token', () => {
    const requestInterceptor = api.interceptors.request.handlers[0].fulfilled
    const config = requestInterceptor({ headers: {} })

    expect(config.headers.Authorization).toBeUndefined()
  })

  it('refreshes token on 401 and retries the request', async () => {
    const authStore = useAuthStore()
    authStore.refreshToken = 'old-refresh'

    api.defaults.adapter = vi.fn(async (config) => {
      if (config.url === '/api/v1/auth/refresh') {
        return makeResponse(config, { access_token: 'new-token', refresh_token: 'new-refresh' })
      }
      return makeResponse(config, { data: [] })
    })

    const responseInterceptor = api.interceptors.response.handlers[0].rejected
    const error = {
      response: { status: 401 },
      config: { url: '/protected', headers: {} },
    }

    const result = await responseInterceptor(error)

    expect(authStore.token).toBe('new-token')
    expect(result.config.headers.Authorization).toBe('Bearer new-token')
  })

  it('logs out when refresh fails', async () => {
    const authStore = useAuthStore()
    authStore.refreshToken = 'old-refresh'

    api.defaults.adapter = vi.fn(async (config) => {
      if (config.url === '/api/v1/auth/refresh') {
        return Promise.reject(new Error('Refresh failed'))
      }
      return makeResponse(config)
    })

    const responseInterceptor = api.interceptors.response.handlers[0].rejected
    const error = {
      response: { status: 401 },
      config: { url: '/protected', headers: {} },
    }

    await expect(responseInterceptor(error)).rejects.toThrow('Refresh failed')
    expect(authStore.token).toBeNull()
  })

  it('uses VITE_API_URL (build-time) as the base URL', () => {
    // The API client must source its endpoint from the Vite build-time
    // variable import.meta.env.VITE_API_URL, falling back to localhost only
    // in development. This guards against regressions that would break the
    // production build-time contract enforced by web/Dockerfile.prod.
    const expected = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    expect(api.defaults.baseURL).toBe(expected)
  })

  // -----------------------------------------------------------------------
  // P0 white-screen: timeout + refresh-no-loop regression tests
  // -----------------------------------------------------------------------

  it('configures a finite request timeout (no infinite hang)', () => {
    expect(api.defaults.timeout).toBeGreaterThan(0)
    expect(api.defaults.timeout).toBeLessThanOrEqual(30000)
  })

  it('não tenta refresh recursivo na rota /auth/refresh', async () => {
    const authStore = useAuthStore()
    authStore.token = 'expired'
    authStore.refreshToken = 'expired-refresh'

    api.defaults.adapter = vi.fn(async (config) => {
      // /auth/refresh itself returns 401 — must NOT trigger another refresh
      return Promise.reject({
        response: { status: 401 },
        config,
      })
    })

    const responseInterceptor = api.interceptors.response.handlers[0].rejected
    const error = {
      response: { status: 401 },
      config: { url: '/api/v1/auth/refresh', headers: {} },
    }

    await expect(responseInterceptor(error)).rejects.toBeDefined()
    // The refresh call should not have been attempted (no recursive loop)
    expect(authStore.token).toBe('expired') // not cleared by interceptor
  })

  it('não redireciona para /login quando em página pública e refresh falha', async () => {
    const authStore = useAuthStore()
    authStore.token = 'expired'
    authStore.refreshToken = 'expired-refresh'

    // Simulate being on a public page
    const originalPathname = window.location.pathname
    Object.defineProperty(window, 'location', {
      value: { pathname: '/', href: 'http://localhost/' },
      writable: true,
    })

    api.defaults.adapter = vi.fn(async (config) => {
      if (config.url === '/api/v1/auth/refresh') {
        return Promise.reject(new Error('Refresh failed'))
      }
      return makeResponse(config)
    })

    const responseInterceptor = api.interceptors.response.handlers[0].rejected
    const error = {
      response: { status: 401 },
      config: { url: '/protected', headers: {} },
    }

    await expect(responseInterceptor(error)).rejects.toThrow('Refresh failed')
    expect(authStore.token).toBeNull() // session cleared
    expect(window.location.href).toBe('http://localhost/') // NOT redirected to /login

    // Restore
    Object.defineProperty(window, 'location', {
      value: { pathname: originalPathname, href: window.location.href },
      writable: true,
    })
  })

  it('redireciona para /login quando em página protegida e refresh falha', async () => {
    const authStore = useAuthStore()
    authStore.token = 'expired'
    authStore.refreshToken = 'expired-refresh'

    Object.defineProperty(window, 'location', {
      value: { pathname: '/dashboard', href: 'http://localhost/dashboard' },
      writable: true,
    })

    api.defaults.adapter = vi.fn(async (config) => {
      if (config.url === '/api/v1/auth/refresh') {
        return Promise.reject(new Error('Refresh failed'))
      }
      return makeResponse(config)
    })

    const responseInterceptor = api.interceptors.response.handlers[0].rejected
    const error = {
      response: { status: 401 },
      config: { url: '/protected', headers: {} },
    }

    await expect(responseInterceptor(error)).rejects.toThrow('Refresh failed')
    expect(authStore.token).toBeNull()
    expect(window.location.href).toBe('/login')
  })
})
