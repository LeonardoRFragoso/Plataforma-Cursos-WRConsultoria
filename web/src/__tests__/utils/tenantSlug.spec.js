import { describe, it, expect, afterEach, vi } from 'vitest'

describe('tenantSlug resolver', () => {
  const originalWindow = global.window

  afterEach(() => {
    global.window = originalWindow
    vi.resetModules()
  })

  async function importFresh() {
    return (await import('../../utils/tenantSlug'))
  }

  it('returns VITE_TENANT_SLUG override when set', async () => {
    vi.stubEnv('VITE_TENANT_SLUG', 'alfa')
    const mod = await importFresh()
    expect(mod.resolveFrontendTenantSlug()).toBe('alfa')
  })

  it('derives slug from hostname subdomain', async () => {
    vi.stubEnv('VITE_TENANT_SLUG', '')
    global.window = { location: { hostname: 'alfa-demo.vercel.app' } }
    const mod = await importFresh()
    expect(mod.resolveFrontendTenantSlug()).toBe('alfa-demo')
  })

  it('returns wr for localhost', async () => {
    vi.stubEnv('VITE_TENANT_SLUG', '')
    global.window = { location: { hostname: 'localhost' } }
    const mod = await importFresh()
    expect(mod.resolveFrontendTenantSlug()).toBe('wr')
  })

  it('returns wr for 127.0.0.1', async () => {
    vi.stubEnv('VITE_TENANT_SLUG', '')
    global.window = { location: { hostname: '127.0.0.1' } }
    const mod = await importFresh()
    expect(mod.resolveFrontendTenantSlug()).toBe('wr')
  })

  it('returns wr for two-part domain', async () => {
    vi.stubEnv('VITE_TENANT_SLUG', '')
    global.window = { location: { hostname: 'example.com' } }
    const mod = await importFresh()
    expect(mod.resolveFrontendTenantSlug()).toBe('wr')
  })

  it('returns wr fallback when no window', async () => {
    vi.stubEnv('VITE_TENANT_SLUG', '')
    global.window = undefined
    const mod = await importFresh()
    expect(mod.resolveFrontendTenantSlug()).toBe('wr')
  })

  it('lowercases the override', async () => {
    vi.stubEnv('VITE_TENANT_SLUG', 'ALFA')
    const mod = await importFresh()
    expect(mod.resolveFrontendTenantSlug()).toBe('alfa')
  })
})
