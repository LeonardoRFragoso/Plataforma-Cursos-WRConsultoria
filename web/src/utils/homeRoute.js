/**
 * Centralized role-aware home resolver.
 *
 * Single source of truth for where a user should land when clicking the
 * application logo, the "home" CTA, or after login/register. Every
 * component and route guard that needs a "home" destination MUST call
 * `getHomeRoute()` instead of hardcoding `/` or `/dashboard`.
 *
 * Rules:
 *   PUBLIC (no token / not authenticated) → /
 *   STUDENT                               → /dashboard
 *   ADMIN                                 → /dashboard
 *   SUPER_ADMIN                           → /super-admin
 *
 * The function accepts either an auth store instance (preferred) or a
 * plain role string, so it is usable from route guards, components,
 * and unit tests without pinia boilerplate.
 */

/**
 * Resolve the role string from the given auth store or role value.
 * Returns a lowercased role or null.
 * @param {object|string|null} authOrRole - auth store instance or role string
 * @returns {string|null}
 */
function resolveRole(authOrRole) {
  if (!authOrRole) return null
  if (typeof authOrRole === 'string') return authOrRole.toLowerCase()
  // auth store shape: { userRole, isAuthenticated, token }
  if (!authOrRole.isAuthenticated && !authOrRole.token) return null
  const role = authOrRole.userRole
  return role ? role.toLowerCase() : null
}

/**
 * Return the home route for the given auth context.
 * @param {object|string|null} authOrRole - auth store instance or role string
 * @returns {string} - a route path
 */
export function getHomeRoute(authOrRole) {
  const role = resolveRole(authOrRole)
  if (!role) return '/'
  if (role === 'super_admin') return '/super-admin'
  // student and admin both go to /dashboard
  return '/dashboard'
}

/**
 * Return the home route for a role string only (no auth store).
 * Convenience wrapper for cases where only the role is known.
 * @param {string|null} role
 * @returns {string}
 */
export function getHomeRouteForRole(role) {
  return getHomeRoute(role)
}

export default getHomeRoute
