/**
 * Safe internal redirect resolver.
 *
 * Validates that a redirect target is:
 * 1. An internal path (no external URLs, no protocol-relative URLs)
 * 2. Not a javascript: URI
 * 3. Allowed for the current user's role
 *
 * If any check fails, falls back to getHomeRoute(authStore).
 */
import { getHomeRoute } from './homeRoute'

// Routes that require admin or super_admin role
const ADMIN_ROUTES = [
  '/courses',
  '/classes',
  '/students',
  '/enrollments',
  '/payments',
  '/settings/white-label',
]

// Routes that require super_admin role
const SUPER_ADMIN_ROUTES = [
  '/super-admin',
]

// Routes allowed for any authenticated user
const AUTHENTICATED_ROUTES = [
  '/dashboard',
  '/certificates',
]

/**
 * Check if a redirect string is a safe internal path.
 * Rejects external URLs, protocol-relative URLs, and javascript: URIs.
 * @param {string} redirect
 * @returns {boolean}
 */
export function isSafeInternalRedirect(redirect) {
  if (!redirect || typeof redirect !== 'string') return false

  // Reject empty or whitespace-only
  const trimmed = redirect.trim()
  if (!trimmed) return false

  // Must start with / (internal path)
  if (!trimmed.startsWith('/')) return false

  // Reject protocol-relative URLs (//evil.example)
  if (trimmed.startsWith('//')) return false

  // Reject javascript: URIs (case-insensitive)
  if (/^javascript:/i.test(trimmed)) return false

  // Reject data: URIs
  if (/^data:/i.test(trimmed)) return false

  // Reject any protocol:// (http://, https://, ftp://, etc.)
  if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed)) return false

  // Must be a valid path-like string (alphanumeric, /, -, _, ., ?, =, &)
  if (!/^[a-zA-Z0-9\-_/.?=&%]+$/.test(trimmed)) return false

  return true
}

/**
 * Check if a path is allowed for the given role.
 * @param {string} path - the redirect path
 * @param {string|null} role - lowercased role
 * @returns {boolean}
 */
export function isAllowedForRole(path, role) {
  if (!role) return false

  // Super admin can access everything
  if (role === 'super_admin') return true

  // Course learn route is allowed for any authenticated user (check before admin routes)
  if (/^\/courses\/[^/]+\/learn$/.test(path)) return true

  // Check admin-only routes
  const isAdminRoute = ADMIN_ROUTES.some((r) => path === r || path.startsWith(r + '/'))
  if (isAdminRoute) {
    return role === 'admin'
  }

  // Check super-admin-only routes
  const isSuperAdminRoute = SUPER_ADMIN_ROUTES.some((r) => path === r || path.startsWith(r + '/'))
  if (isSuperAdminRoute) {
    return role === 'super_admin'
  }

  // Authenticated routes are allowed for any authenticated user
  const isAuthRoute = AUTHENTICATED_ROUTES.some((r) => path === r || path.startsWith(r + '/'))
  if (isAuthRoute) return true

  // Public routes are allowed for authenticated users too
  if (path === '/' || path === '/cursos' || /^\/cursos\/[^/]+$/.test(path)) return true

  // Demo payment route is allowed for any authenticated user
  if (/^\/demo\/payment\/[^/]+$/.test(path)) return true

  // If we can't determine, be conservative and reject
  return false
}

/**
 * Resolve a safe redirect target.
 * @param {string|null} redirect - the requested redirect
 * @param {object|string|null} authOrRole - auth store instance or role string
 * @returns {string} - a safe route path
 */
export function resolveSafeRedirect(redirect, authOrRole) {
  const role = typeof authOrRole === 'string'
    ? authOrRole.toLowerCase()
    : (authOrRole?.userRole?.toLowerCase() || null)

  // Step 1: Check if redirect is a safe internal path
  if (!isSafeInternalRedirect(redirect)) {
    return getHomeRoute(authOrRole)
  }

  // Step 2: Check if the path is allowed for the role
  if (!isAllowedForRole(redirect, role)) {
    return getHomeRoute(authOrRole)
  }

  return redirect
}

export default resolveSafeRedirect
