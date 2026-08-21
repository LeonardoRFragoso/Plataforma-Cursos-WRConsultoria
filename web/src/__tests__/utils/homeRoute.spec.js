import { describe, it, expect } from 'vitest'
import { getHomeRoute, getHomeRouteForRole } from '../../utils/homeRoute'

describe('homeRoute resolver', () => {
  describe('getHomeRouteForRole', () => {
    it('returns / for null role (public)', () => {
      expect(getHomeRouteForRole(null)).toBe('/')
    })

    it('returns / for undefined role (public)', () => {
      expect(getHomeRouteForRole(undefined)).toBe('/')
    })

    it('returns / for empty string role (public)', () => {
      expect(getHomeRouteForRole('')).toBe('/')
    })

    it('returns /dashboard for student', () => {
      expect(getHomeRouteForRole('student')).toBe('/dashboard')
    })

    it('returns /dashboard for STUDENT (case insensitive)', () => {
      expect(getHomeRouteForRole('STUDENT')).toBe('/dashboard')
    })

    it('returns /dashboard for admin', () => {
      expect(getHomeRouteForRole('admin')).toBe('/dashboard')
    })

    it('returns /dashboard for ADMIN (case insensitive)', () => {
      expect(getHomeRouteForRole('ADMIN')).toBe('/dashboard')
    })

    it('returns /super-admin for super_admin', () => {
      expect(getHomeRouteForRole('super_admin')).toBe('/super-admin')
    })

    it('returns /super-admin for SUPER_ADMIN (case insensitive)', () => {
      expect(getHomeRouteForRole('SUPER_ADMIN')).toBe('/super-admin')
    })
  })

  describe('getHomeRoute with auth store shape', () => {
    it('returns / when not authenticated (no token)', () => {
      const auth = { isAuthenticated: false, token: null, userRole: null }
      expect(getHomeRoute(auth)).toBe('/')
    })

    it('returns / when not authenticated (token but not authenticated flag)', () => {
      const auth = { isAuthenticated: false, token: null, userRole: 'student' }
      expect(getHomeRoute(auth)).toBe('/')
    })

    it('returns /dashboard for authenticated student', () => {
      const auth = { isAuthenticated: true, token: 'tok', userRole: 'student' }
      expect(getHomeRoute(auth)).toBe('/dashboard')
    })

    it('returns /dashboard for authenticated admin', () => {
      const auth = { isAuthenticated: true, token: 'tok', userRole: 'admin' }
      expect(getHomeRoute(auth)).toBe('/dashboard')
    })

    it('returns /super-admin for authenticated super_admin', () => {
      const auth = { isAuthenticated: true, token: 'tok', userRole: 'super_admin' }
      expect(getHomeRoute(auth)).toBe('/super-admin')
    })

    it('handles token-based auth check when isAuthenticated is missing', () => {
      const auth = { token: 'tok', userRole: 'admin' }
      expect(getHomeRoute(auth)).toBe('/dashboard')
    })

    it('returns / when no token and no isAuthenticated', () => {
      const auth = { userRole: 'admin' }
      expect(getHomeRoute(auth)).toBe('/')
    })
  })

  describe('getHomeRoute with plain string', () => {
    it('returns /dashboard for student string', () => {
      expect(getHomeRoute('student')).toBe('/dashboard')
    })

    it('returns /super-admin for super_admin string', () => {
      expect(getHomeRoute('super_admin')).toBe('/super-admin')
    })

    it('returns / for null', () => {
      expect(getHomeRoute(null)).toBe('/')
    })
  })
})
