import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTenantStore } from '../../stores/tenant'

vi.mock('../../api/tenant', () => ({
  fetchTenantBranding: vi.fn(),
  updateTenantBranding: vi.fn(),
}))

describe('Tenant Store — applyFavicon', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // Clean up DOM
    document.head.innerHTML = ''
  })

  it('creates favicon link element when none exists', () => {
    const store = useTenantStore()
    store.favicon_url = 'https://example.com/favicon.ico'

    expect(document.querySelector("link[rel~='icon']")).toBeNull()

    store.applyFavicon()

    const link = document.querySelector("link[rel~='icon']")
    expect(link).not.toBeNull()
    expect(link.href).toBe('https://example.com/favicon.ico')
  })

  it('updates existing favicon link element', () => {
    const existing = document.createElement('link')
    existing.rel = 'icon'
    existing.href = 'https://old.com/favicon.ico'
    document.head.appendChild(existing)

    const store = useTenantStore()
    store.favicon_url = 'https://new.com/favicon.ico'

    store.applyFavicon()

    const link = document.querySelector("link[rel~='icon']")
    expect(link.href).toBe('https://new.com/favicon.ico')
    expect(document.querySelectorAll("link[rel~='icon']")).toHaveLength(1)
  })

  it('does nothing when favicon_url is null', () => {
    const store = useTenantStore()
    store.favicon_url = null

    store.applyFavicon()

    expect(document.querySelector("link[rel~='icon']")).toBeNull()
  })

  it('does nothing when favicon_url is empty', () => {
    const store = useTenantStore()
    store.favicon_url = ''

    store.applyFavicon()

    expect(document.querySelector("link[rel~='icon']")).toBeNull()
  })
})

describe('Tenant Store — applyColors', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.documentElement.style.cssText = ''
  })

  it('applies primary color to CSS variable', () => {
    const store = useTenantStore()
    store.primary_color = '#E86A17'

    store.applyColors()

    expect(document.documentElement.style.getPropertyValue('--color-primary')).toBe('#E86A17')
  })

  it('applies all three colors', () => {
    const store = useTenantStore()
    store.primary_color = '#E86A17'
    store.secondary_color = '#1F2937'
    store.accent_color = '#FBBF24'

    store.applyColors()

    expect(document.documentElement.style.getPropertyValue('--color-primary')).toBe('#E86A17')
    expect(document.documentElement.style.getPropertyValue('--color-secondary')).toBe('#1F2937')
    expect(document.documentElement.style.getPropertyValue('--color-accent')).toBe('#FBBF24')
  })

  it('skips null colors', () => {
    const store = useTenantStore()
    store.primary_color = null
    store.secondary_color = null
    store.accent_color = null

    store.applyColors()

    // When colors are null, applyColors falls back to INITIAL_FALLBACK which
    // is WR_DEFAULTS (test env resolves TENANT_SLUG to 'wr').
    expect(document.documentElement.style.getPropertyValue('--color-primary')).toBe('#047F37')
  })
})

describe('Tenant Store — loadBranding', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads branding data from API', async () => {
    const { fetchTenantBranding } = await import('../../api/tenant')
    fetchTenantBranding.mockResolvedValue({
      name: 'Alfa Academy',
      logo_url: 'https://alfa.com/logo.png',
      logo_white_url: null,
      favicon_url: 'https://alfa.com/favicon.ico',
      primary_color: '#E86A17',
      secondary_color: '#1F2937',
      accent_color: '#FBBF24',
    })

    const store = useTenantStore()
    await store.loadBranding('alfa')

    expect(store.name).toBe('Alfa Academy')
    expect(store.primary_color).toBe('#E86A17')
    expect(store.loaded).toBe(true)
  })

  it('falls back to defaults on API error', async () => {
    const { fetchTenantBranding } = await import('../../api/tenant')
    fetchTenantBranding.mockRejectedValue(new Error('Network error'))

    const store = useTenantStore()
    await store.loadBranding('alfa')

    expect(store.name).toBe('Plataforma de Cursos')
    // DEFAULTS.primary was updated to WR green (#1B7A3A) to match the
    // WR brand colors used as the platform-wide neutral fallback.
    expect(store.primary_color).toBe('#1B7A3A')
    expect(store.loaded).toBe(true)
  })
})

describe('Tenant Store — WR premium branding (tenant-based, not role-based)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.documentElement.style.cssText = ''
    vi.clearAllMocks()
  })

  it('WR tenant: API branding applies #047F37 as --brand-primary', async () => {
    const { fetchTenantBranding } = await import('../../api/tenant')
    fetchTenantBranding.mockResolvedValue({
      name: 'WR Consultoria e Soluções em QSMS',
      logo_url: null, logo_white_url: null, favicon_url: null,
      primary_color: '#047F37',
      secondary_color: '#17324D',
      accent_color: '#F59E0B',
    })

    const store = useTenantStore()
    await store.loadBranding('wr')

    expect(store.primary_color).toBe('#047F37')
    expect(document.documentElement.style.getPropertyValue('--brand-primary')).toBe('#047F37')
    expect(document.documentElement.style.getPropertyValue('--color-primary')).toBe('#047F37')
  })

  it('WR tenant: fallback applies #047F37 when API is unavailable', async () => {
    const { fetchTenantBranding } = await import('../../api/tenant')
    fetchTenantBranding.mockRejectedValue(new Error('Network error'))

    const store = useTenantStore()
    await store.loadBranding('wr')

    expect(store.primary_color).toBe('#047F37')
    expect(document.documentElement.style.getPropertyValue('--brand-primary')).toBe('#047F37')
  })

  it('WR tenant: initial state has #047F37 (no flash of wrong color)', () => {
    const store = useTenantStore()
    // IS_WR is true in test env (localhost → 'wr'), so initial state
    // should already have the WR premium green.
    expect(store.primary_color).toBe('#047F37')
  })

  it('non-WR tenant: API branding does NOT receive #047F37', async () => {
    const { fetchTenantBranding } = await import('../../api/tenant')
    fetchTenantBranding.mockResolvedValue({
      name: 'Alfa Academy',
      logo_url: null, logo_white_url: null, favicon_url: null,
      primary_color: '#E86A17',
      secondary_color: '#1F2937',
      accent_color: '#FBBF24',
    })

    const store = useTenantStore()
    await store.loadBranding('alfa')

    expect(store.primary_color).not.toBe('#047F37')
    expect(store.primary_color).toBe('#E86A17')
    expect(document.documentElement.style.getPropertyValue('--brand-primary')).toBe('#E86A17')
  })

  it('non-WR tenant: fallback does NOT use #047F37', async () => {
    const { fetchTenantBranding } = await import('../../api/tenant')
    fetchTenantBranding.mockRejectedValue(new Error('Network error'))

    const store = useTenantStore()
    await store.loadBranding('alfa')

    expect(store.primary_color).not.toBe('#047F37')
  })

  it('branding is tenant-based: same color regardless of user role', async () => {
    // The tenant store has no concept of user role. The same branding
    // (including primary_color) is applied for admin, student, and any
    // other role within the same tenant. This test proves the color
    // comes from the tenant, not from the user's role.
    const { fetchTenantBranding } = await import('../../api/tenant')
    fetchTenantBranding.mockResolvedValue({
      name: 'WR Consultoria e Soluções em QSMS',
      logo_url: null, logo_white_url: null, favicon_url: null,
      primary_color: '#047F37',
      secondary_color: '#17324D',
      accent_color: '#F59E0B',
    })

    const store = useTenantStore()
    await store.loadBranding('wr')

    // The store has no role field — branding is purely tenant-based.
    // Admin, student, super_admin all get the same --brand-primary.
    expect(store.primary_color).toBe('#047F37')
    expect(document.documentElement.style.getPropertyValue('--brand-primary')).toBe('#047F37')
  })
})
