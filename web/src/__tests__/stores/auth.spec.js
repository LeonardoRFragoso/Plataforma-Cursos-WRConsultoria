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

  it('recognizes student role', () => {
    const authStore = useAuthStore()
    authStore.userRole = 'student'

    expect(authStore.userRole).toBe('student')
  })
})
