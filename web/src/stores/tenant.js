import { defineStore } from 'pinia'
import { fetchTenantBranding } from '../api/tenant'
import { TENANT_SLUG } from '../utils/tenantSlug'

const DEFAULTS = {
  name: 'Plataforma de Cursos',
  primary: '#1B7A3A',
  secondary: '#17324D',
  accent: '#F59E0B',
}

const WR_DEFAULTS = {
  name: 'WR Consultoria e Soluções em QSMS',
  primary: '#047F37',
  secondary: '#17324D',
  accent: '#F59E0B',
}

const fallbackFor = (slug = TENANT_SLUG) =>
  String(slug || '').toLowerCase() === 'wr' ? WR_DEFAULTS : DEFAULTS

const normalizeHex = (value, fallback) => {
  if (typeof value !== 'string') return fallback
  const hex = value.trim()
  return /^#[0-9a-fA-F]{6}$/.test(hex) ? hex : fallback
}

const INITIAL_FALLBACK = fallbackFor(TENANT_SLUG)
const IS_WR = TENANT_SLUG === 'wr'

export const useTenantStore = defineStore('tenant', {
  state: () => ({
    // WR has a stable local identity so public pages never flash generic
    // branding or remain stuck on "Carregando..." while Railway wakes up.
    // Partner tenants still wait for their own API-provided branding.
    name: IS_WR ? WR_DEFAULTS.name : '',
    logo_url: null,
    logo_white_url: null,
    favicon_url: null,
    primary_color: IS_WR ? WR_DEFAULTS.primary : null,
    secondary_color: IS_WR ? WR_DEFAULTS.secondary : null,
    accent_color: IS_WR ? WR_DEFAULTS.accent : null,
    loading: false,
    loaded: IS_WR,
  }),

  actions: {
    async loadBranding(slug = TENANT_SLUG) {
      const fallback = fallbackFor(slug)
      this.loading = true
      try {
        const data = await fetchTenantBranding(slug)
        this.name = data.name || fallback.name
        this.logo_url = data.logo_url
        this.logo_white_url = data.logo_white_url
        this.favicon_url = data.favicon_url
        this.primary_color = normalizeHex(data.primary_color, fallback.primary)
        this.secondary_color = normalizeHex(data.secondary_color, fallback.secondary)
        this.accent_color = normalizeHex(data.accent_color, fallback.accent)
        this.loaded = true
      } catch {
        // Keep a deterministic local fallback instead of exposing the generic
        // platform identity when the branding endpoint is slow/unavailable.
        this.name = fallback.name
        this.primary_color = fallback.primary
        this.secondary_color = fallback.secondary
        this.accent_color = fallback.accent
        this.loaded = true
      } finally {
        this.loading = false
        this.applyColors(fallback)
      }
    },

    async refreshBranding(slug = TENANT_SLUG) {
      await this.loadBranding(slug)
      const fallback = fallbackFor(slug)
      const name = this.name || fallback.name
      document.title = name
      this.applyFavicon()
    },

    applyColors(fallback = INITIAL_FALLBACK) {
      if (typeof document === 'undefined') return
      const root = document.documentElement
      const primary = normalizeHex(this.primary_color, fallback.primary)
      const secondary = normalizeHex(this.secondary_color, fallback.secondary)
      const accent = normalizeHex(this.accent_color, fallback.accent)
      root.style.setProperty('--color-primary', primary)
      root.style.setProperty('--color-secondary', secondary)
      root.style.setProperty('--color-accent', accent)
      root.style.setProperty('--brand-primary', primary)
      root.style.setProperty('--brand-secondary', secondary)
      root.style.setProperty('--brand-accent', accent)
      root.dataset.tenantBrand = 'ready'
    },

    applyFavicon() {
      if (!this.favicon_url || typeof document === 'undefined') return
      let link = document.querySelector("link[rel~='icon']")
      if (!link) {
        link = document.createElement('link')
        link.rel = 'icon'
        document.head.appendChild(link)
      }
      link.href = this.favicon_url
    },
  },
})
