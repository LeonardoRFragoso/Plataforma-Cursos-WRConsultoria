/**
 * Central tenant slug resolution for the frontend.
 *
 * Priority:
 *   1. VITE_TENANT_SLUG build-time override
 *   2. hostname-derived slug (first subdomain segment)
 *   3. "wr" fallback
 *
 * Used both for API requests (X-Tenant-Slug header) and for the
 * branding lookup (?slug=...).
 */

const DEV_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0"])

function hostnameToSlug(hostname) {
  if (!hostname) return "wr"
  const host = hostname.split(":")[0].toLowerCase()
  if (DEV_HOSTS.has(host)) return "wr"
  const parts = host.split(".")
  if (parts.length >= 3) return parts[0]
  if (parts.length === 2) return "wr"
  return "wr"
}

export function resolveFrontendTenantSlug() {
  // Build-time override wins (useful for separate Vercel projects whose
  // generated domains don't match the tenant slug).
  const override = import.meta.env.VITE_TENANT_SLUG
  if (override && override.trim()) return override.trim().toLowerCase()

  // Derive from browser hostname.
  if (typeof window !== "undefined" && window.location) {
    return hostnameToSlug(window.location.hostname)
  }

  return "wr"
}

// Eagerly compute once so all callers see the same value within a page load.
export const TENANT_SLUG = resolveFrontendTenantSlug()
