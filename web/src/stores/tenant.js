import { defineStore } from 'pinia'
import { fetchTenantBranding } from '../api/tenant'

const DEFAULTS = {
  name: 'Plataforma de Cursos',
  primary: '#1B7A3A',
  secondary: '#17324D',
  accent: '#F59E0B',
}

const normalizeHex = (value, fallback) => {
  if (typeof value !== 'string') return fallback
  const hex = value.trim()
  return /^#[0-9a-fA-F]{6}$/.test(hex) ? hex : fallback
}

export const useTenantStore = defineStore('tenant', {
  state: () => ({
    name: '',
    logo_url: null,
    logo_white_url: null,
    favicon_url: null,
    primary_color: null,
    secondary_color: null,
    accent_color: null,
    loading: false,
    loaded: false,
  }),

  actions: {
    async loadBranding(slug = 'wr') {
      this.loading = true
      try {
        const data = await fetchTenantBranding(slug)
        this.name = data.name
        this.logo_url = data.logo_url
        this.logo_white_url = data.logo_white_url
        this.favicon_url = data.favicon_url
        this.primary_color = normalizeHex(data.primary_color, DEFAULTS.primary)
        this.secondary_color = normalizeHex(data.secondary_color, DEFAULTS.secondary)
        this.accent_color = normalizeHex(data.accent_color, DEFAULTS.accent)
        this.loaded = true
      } catch {
        this.name = DEFAULTS.name
        this.primary_color = DEFAULTS.primary
        this.secondary_color = DEFAULTS.secondary
        this.accent_color = DEFAULTS.accent
        this.loaded = true
      } finally {
        this.loading = false
        this.applyColors()
      }
    },

    async refreshBranding(slug) {
      await this.loadBranding(slug)
      const name = this.name || DEFAULTS.name
      document.title = name
      this.applyFavicon()
    },

    applyColors() {
      if (typeof document === 'undefined') return
      const root = document.documentElement
      const primary = normalizeHex(this.primary_color, DEFAULTS.primary)
      const secondary = normalizeHex(this.secondary_color, DEFAULTS.secondary)
      const accent = normalizeHex(this.accent_color, DEFAULTS.accent)
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
