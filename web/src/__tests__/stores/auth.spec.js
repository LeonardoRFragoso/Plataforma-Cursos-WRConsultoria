import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
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

  it('stores token in localStorage on login', () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.refreshToken = 'refresh-token'
    authStore.userRole = 'student'
    
    expect(localStorage.getItem('access_token')).toBe('test-token')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-token')
    expect(localStorage.getItem('user_role')).toBe('student')
  })

  it('recognizes admin role', () => {
    const authStore = useAuthStore()
    authStore.userRole = 'admin'
    
    expect(authStore.userRole).toBe('admin')
  })

  it('recognizes instructor role', () => {
    const authStore = useAuthStore()
    authStore.userRole = 'instructor'
    
    expect(authStore.userRole).toBe('instructor')
  })

  it('recognizes student role', () => {
    const authStore = useAuthStore()
    authStore.userRole = 'student'
    
    expect(authStore.userRole).toBe('student')
  })
})
