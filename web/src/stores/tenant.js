import { defineStore } from 'pinia'
import { fetchTenantBranding } from '../api/tenant'

export const useTenantStore = defineStore('tenant', {
  state: () => ({
    name: '',
    logo_url: null,
    logo_white_url: null,
    favicon_url: null,
    primary_color: null,
    secondary_color: null,
    accent_color: null,
    loaded: false,
  }),

  actions: {
    async loadBranding(slug = 'wr') {
      try {
        const data = await fetchTenantBranding(slug)
        this.name = data.name
        this.logo_url = data.logo_url
        this.logo_white_url = data.logo_white_url
        this.favicon_url = data.favicon_url
        this.primary_color = data.primary_color
        this.secondary_color = data.secondary_color
        this.accent_color = data.accent_color
        this.loaded = true
      } catch (error) {
        this.name = 'WR Consultoria'
        this.primary_color = '#0056b3'
        this.secondary_color = '#1a1a1a'
        this.accent_color = '#ff6b35'
        this.loaded = true
      }
    },

    applyColors() {
      const root = document.documentElement
      if (this.primary_color) root.style.setProperty('--color-primary', this.primary_color)
      if (this.secondary_color) root.style.setProperty('--color-secondary', this.secondary_color)
      if (this.accent_color) root.style.setProperty('--color-accent', this.accent_color)
    },
  },
})
