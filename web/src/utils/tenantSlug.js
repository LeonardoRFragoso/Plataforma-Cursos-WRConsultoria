/**
 * Central tenant slug resolution for the frontend.
 *
 * Priority:
 *   1. VITE_TENANT_SLUG build-time override
 *   2. known Vercel project hostnames (production, branch aliases and previews)
 *   3. hostname-derived slug (first subdomain segment)
 *   4. "wr" fallback
 *
 * Used both for API requests (X-Tenant-Slug header) and for the
 * branding lookup (?slug=...).
 */

const DEV_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0"])

// Vercel generates immutable deployment URLs and branch aliases by appending
// hashes/branch identifiers to the project name. Those hostnames must still
// resolve to the tenant configured for the project; otherwise a WR preview
// becomes a generic "Plataforma de Cursos" frontend and sends the wrong
// X-Tenant-Slug to the API.
const VERCEL_PROJECT_TENANTS = [
  { project: "wr-cursos-demo", tenant: "wr" },
  { project: "alfa-academy-demo", tenant: "alfa" },
]

function knownVercelProjectTenant(host) {
  if (!host.endsWith(".vercel.app")) return null
  const firstLabel = host.split(".")[0]

  for (const { project, tenant } of VERCEL_PROJECT_TENANTS) {
    if (firstLabel === project || firstLabel.startsWith(`${project}-`)) {
      return tenant
    }
  }

  return null
}

function hostnameToSlug(hostname) {
  if (!hostname) return "wr"
  const host = hostname.split(":")[0].toLowerCase()
  if (DEV_HOSTS.has(host)) return "wr"

  const knownTenant = knownVercelProjectTenant(host)
  if (knownTenant) return knownTenant

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
