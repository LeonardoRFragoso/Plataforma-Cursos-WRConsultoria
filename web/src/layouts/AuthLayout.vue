<template>
  <div class="min-h-screen flex flex-col lg:flex-row" data-testid="auth-layout">
    <!-- ────────────────────────────────────────────────────────────
         VISUAL PANEL (desktop only — hidden on mobile to prioritize form)
         WR: dedicated auth crop (photographic right side of hero, no
         embedded marketing text). Non-WR: tenant-color gradient fallback.
         No /assets/wr/ reference for non-WR tenants.
    ──────────────────────────────────────────────────────────── -->
    <div
      class="hidden lg:flex lg:w-[52%] xl:w-[55%] relative overflow-hidden"
      data-testid="auth-visual-panel"
    >
      <!-- WR tenant: dedicated auth crop (workers/training, no embedded headline) -->
      <img
        v-if="authVisual"
        :src="authVisual.src"
        :alt="authVisual.alt"
        class="absolute inset-0 w-full h-full object-cover"
        data-testid="auth-visual-img"
      />
      <!-- Non-WR fallback: tenant-color gradient (no WR imagery) -->
      <div
        v-else
        class="absolute inset-0"
        :style="gradientStyle"
        data-testid="auth-visual-fallback"
      ></div>

      <!-- Dark green overlay for depth and text legibility (WR only) -->
      <div
        v-if="authVisual"
        class="absolute inset-0 bg-gradient-to-br from-primary-900/40 via-transparent to-primary-900/60"
      ></div>

      <!-- Tenant brand at top of visual panel -->
      <div class="absolute top-0 left-0 right-0 p-10 xl:p-14">
        <p class="text-white/90 text-sm font-semibold tracking-wide drop-shadow-lg">
          {{ tenantStore.name || 'Plataforma de Cursos' }}
        </p>
      </div>

      <!-- Tagline at bottom — clean photographic area, no embedded text collision -->
      <div class="absolute bottom-0 left-0 right-0 p-10 xl:p-14">
        <p class="text-white text-xl xl:text-2xl font-semibold leading-snug drop-shadow-lg">
          Capacitação que transforma<br />segurança em prática.
        </p>
      </div>
    </div>

    <!-- ────────────────────────────────────────────────────────────
         FORM PANEL
         Centered, controlled width. The form itself stays max-w-md.
    ──────────────────────────────────────────────────────────── -->
    <div class="flex-1 flex flex-col bg-gray-50" data-testid="auth-form-panel">
      <!-- Compact brand header (simplified — no redundant navbar) -->
      <div class="px-6 sm:px-10 pt-8">
        <router-link to="/" class="inline-flex items-center gap-2" data-testid="auth-brand">
          <img
            v-if="tenantStore.logo_url"
            :src="tenantStore.logo_url"
            :alt="tenantStore.name"
            class="h-10 w-auto max-w-[180px] object-contain"
          />
          <span
            v-else-if="tenantStore.loading && !tenantStore.loaded"
            class="text-sm text-gray-400"
            data-testid="auth-brand-loading"
          >
            Carregando…
          </span>
          <span v-else class="text-lg font-bold text-primary-600">
            {{ tenantStore.name || 'Plataforma de Cursos' }}
          </span>
        </router-link>
      </div>

      <!-- Form content slot — each auth view provides its own form -->
      <div class="flex-1 flex items-center justify-center px-6 sm:px-10 py-8">
        <div class="w-full max-w-md" data-testid="auth-form-content">
          <slot />
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 sm:px-10 py-5 text-center text-xs text-gray-400">
        &copy; {{ new Date().getFullYear() }} {{ tenantStore.name || 'Plataforma de Cursos' }}. Todos os direitos reservados.
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * AuthLayout — shared visual shell for authentication pages.
 *
 * Desktop (lg+): 52-55% visual panel (dedicated WR auth crop for WR
 * tenant — photographic right side of hero with no embedded marketing
 * text; neutral tenant-color gradient for others) + 45-48% form panel.
 *
 * Mobile (<lg): visual panel hidden, form panel full-width with compact
 * brand header. The form receives visual priority.
 *
 * White-label isolation: non-WR tenants never see /assets/wr/ imagery.
 */
import { computed } from 'vue'
import { useTenantStore } from '../stores/tenant'
import { getWrAuthVisual } from '../utils/courseMedia'

const tenantStore = useTenantStore()

const authVisual = computed(() => getWrAuthVisual())

const gradientStyle = computed(() => {
  const primary = tenantStore.primary_color || '#0056b3'
  const secondary = tenantStore.secondary_color || '#1a1a1a'
  return {
    background: `linear-gradient(135deg, ${primary}, ${secondary})`,
  }
})
</script>
