import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import api from '../../api/client'

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('initializes with no token', () => {
    const authStore = useAuthStore()
    expect(authStore.token).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('can logout', () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.user = { id: '1', email: 'test@example.com' }

    authStore.logout()

    expect(authStore.token).toBeNull()
    expect(authStore.user).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('stores token in localStorage on login', async () => {
    vi.spyOn(api, 'post')
      .mockResolvedValueOnce({ data: { access_token: 'test-token', refresh_token: 'refresh-token' } })
    vi.spyOn(api, 'get')
      .mockResolvedValueOnce({ data: { role: 'student' } })

    const authStore = useAuthStore()
    await authStore.login('test@example.com', 'password')

    expect(localStorage.getItem('access_token')).toBe('test-token')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-token')
    expect(localStorage.getItem('user_role')).toBe('student')
  })

  it('recognizes admin role', () => {
    const authStore = useAuthStore()
    authStore.userRole = 'admin'

    expect(authStore.userRole).toBe('admin')
  })

  it('can register a new user', async () => {
    vi.spyOn(api, 'post').mockResolvedValueOnce({ data: {} })

    const authStore = useAuthStore()
    await authStore.register('new@example.com', 'New User', 'password')

    expect(api.post).toHaveBeenCalledWith('/api/v1/auth/register', {
      email: 'new@example.com',
      full_name: 'New User',
      password: 'password',
    })
  })

  it('refreshes the access token', async () => {
    vi.spyOn(api, 'post')
      .mockResolvedValueOnce({ data: { access_token: 'new-token', refresh_token: 'new-refresh' } })

    const authStore = useAuthStore()
    authStore.refreshToken = 'old-refresh'

    await authStore.refreshAccessToken()

    expect(authStore.token).toBe('new-token')
    expect(localStorage.getItem('access_token')).toBe('new-token')
  })

  it('does nothing when refreshing without a refresh token', async () => {
    const authStore = useAuthStore()
    await authStore.refreshAccessToken()
    // no errors
  })

  it('logs out when refresh fails', async () => {
    vi.spyOn(api, 'post').mockRejectedValueOnce(new Error('Refresh failed'))

    const authStore = useAuthStore()
    authStore.token = 'token'
    authStore.refreshToken = 'old-refresh'

    await expect(authStore.refreshAccessToken()).rejects.toThrow('Refresh failed')
    expect(authStore.token).toBeNull()
  })

  it('initializes user from backend', async () => {
    vi.spyOn(api, 'get').mockResolvedValueOnce({ data: { role: 'admin', full_name: 'Admin' } })

    const authStore = useAuthStore()
    authStore.token = 'token'

    await authStore.initializeUser()

    expect(authStore.userRole).toBe('admin')
    expect(authStore.initialized).toBe(true)
  })

  it('marks initialized when there is no token', async () => {
    const authStore = useAuthStore()
    await authStore.initializeUser()
    expect(authStore.initialized).toBe(true)
  })

  it('handles initialize user errors gracefully', async () => {
    vi.spyOn(api, 'get').mockRejectedValueOnce(new Error('Server error'))

    const authStore = useAuthStore()
    authStore.token = 'token'

    await authStore.initializeUser()

    expect(authStore.initialized).toBe(true)
  })
})
