import { describe, it, expect } from 'vitest'
import { isSafeInternalRedirect, isAllowedForRole, resolveSafeRedirect } from '../../utils/safeRedirect'

describe('safeRedirect', () => {
  describe('isSafeInternalRedirect', () => {
    it('allows simple internal paths', () => {
      expect(isSafeInternalRedirect('/dashboard')).toBe(true)
      expect(isSafeInternalRedirect('/courses/123/lessons')).toBe(true)
      expect(isSafeInternalRedirect('/cursos')).toBe(true)
    })

    it('rejects external https URLs', () => {
      expect(isSafeInternalRedirect('https://evil.example.com')).toBe(false)
    })

    it('rejects external http URLs', () => {
      expect(isSafeInternalRedirect('http://evil.example.com')).toBe(false)
    })

    it('rejects protocol-relative URLs', () => {
      expect(isSafeInternalRedirect('//evil.example')).toBe(false)
    })

    it('rejects javascript: URIs', () => {
      expect(isSafeInternalRedirect('javascript:alert(1)')).toBe(false)
    })

    it('rejects data: URIs', () => {
      expect(isSafeInternalRedirect('data:text/html,evil')).toBe(false)
    })

    it('rejects empty strings', () => {
      expect(isSafeInternalRedirect('')).toBe(false)
      expect(isSafeInternalRedirect('   ')).toBe(false)
    })

    it('rejects null/undefined', () => {
      expect(isSafeInternalRedirect(null)).toBe(false)
      expect(isSafeInternalRedirect(undefined)).toBe(false)
    })

    it('rejects paths not starting with /', () => {
      expect(isSafeInternalRedirect('dashboard')).toBe(false)
    })
  })

  describe('isAllowedForRole', () => {
    it('allows admin routes for admin', () => {
      expect(isAllowedForRole('/courses', 'admin')).toBe(true)
      expect(isAllowedForRole('/classes', 'admin')).toBe(true)
      expect(isAllowedForRole('/students', 'admin')).toBe(true)
      expect(isAllowedForRole('/enrollments', 'admin')).toBe(true)
      expect(isAllowedForRole('/payments', 'admin')).toBe(true)
      expect(isAllowedForRole('/settings/white-label', 'admin')).toBe(true)
    })

    it('rejects admin routes for student', () => {
      expect(isAllowedForRole('/courses', 'student')).toBe(false)
      expect(isAllowedForRole('/super-admin', 'student')).toBe(false)
    })

    it('rejects super-admin routes for admin', () => {
      expect(isAllowedForRole('/super-admin', 'admin')).toBe(false)
    })

    it('allows super-admin routes for super_admin', () => {
      expect(isAllowedForRole('/super-admin', 'super_admin')).toBe(true)
      expect(isAllowedForRole('/courses', 'super_admin')).toBe(true)
    })

    it('allows authenticated routes for any role', () => {
      expect(isAllowedForRole('/dashboard', 'student')).toBe(true)
      expect(isAllowedForRole('/dashboard', 'admin')).toBe(true)
      expect(isAllowedForRole('/certificates', 'student')).toBe(true)
    })

    it('allows course learn routes for any authenticated user', () => {
      expect(isAllowedForRole('/courses/123/learn', 'student')).toBe(true)
    })

    it('rejects unknown routes', () => {
      expect(isAllowedForRole('/unknown-path', 'student')).toBe(false)
    })

    it('rejects when role is null', () => {
      expect(isAllowedForRole('/dashboard', null)).toBe(false)
    })
  })

  describe('resolveSafeRedirect', () => {
    it('student + redirect=/courses → safe role fallback', () => {
      expect(resolveSafeRedirect('/courses', 'student')).toBe('/dashboard')
    })

    it('student + redirect=/super-admin → safe fallback', () => {
      expect(resolveSafeRedirect('/super-admin', 'student')).toBe('/dashboard')
    })

    it('admin + allowed internal destination → allowed', () => {
      expect(resolveSafeRedirect('/courses', 'admin')).toBe('/courses')
    })

    it('external https URL → rejected, falls back to home', () => {
      expect(resolveSafeRedirect('https://evil.example.com', 'admin')).toBe('/dashboard')
    })

    it('protocol-relative URL → rejected', () => {
      expect(resolveSafeRedirect('//evil.example', 'admin')).toBe('/dashboard')
    })

    it('javascript: URI → rejected', () => {
      expect(resolveSafeRedirect('javascript:alert(1)', 'admin')).toBe('/dashboard')
    })

    it('null redirect → falls back to home', () => {
      expect(resolveSafeRedirect(null, 'student')).toBe('/dashboard')
    })

    it('super_admin + /super-admin → allowed', () => {
      expect(resolveSafeRedirect('/super-admin', 'super_admin')).toBe('/super-admin')
    })

    it('super_admin + /courses → allowed (super_admin can access everything)', () => {
      expect(resolveSafeRedirect('/courses', 'super_admin')).toBe('/courses')
    })
  })
})
