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
})
