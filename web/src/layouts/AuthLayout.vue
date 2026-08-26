<template>
  <div class="min-h-screen lg:grid lg:grid-cols-[1.05fr_.95fr]" data-testid="auth-layout">
    <section class="relative hidden min-h-screen overflow-hidden bg-slate-950 lg:flex" data-testid="auth-visual-panel">
      <img v-if="authVisual" :src="authVisual.src" :alt="authVisual.alt" class="absolute inset-0 h-full w-full object-cover" data-testid="auth-visual-img" />
      <div v-else class="absolute inset-0" :style="gradientStyle" data-testid="auth-visual-fallback"></div>
      <div class="absolute inset-0 bg-gradient-to-br from-slate-950/65 via-slate-950/25 to-slate-950/85"></div>
      <div class="absolute -left-32 top-1/3 h-96 w-96 rounded-full bg-white/[.06] blur-3xl"></div>
      <div class="relative flex w-full flex-col justify-between p-10 xl:p-14">
        <div class="flex items-center gap-3">
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-white/10 p-2 backdrop-blur">
            <img v-if="tenantStore.logo_white_url || tenantStore.logo_url" :src="tenantStore.logo_white_url || tenantStore.logo_url" :alt="tenantStore.name" class="max-h-8 max-w-9 object-contain" />
            <span v-else class="text-sm font-black text-white">{{ initials }}</span>
          </div>
          <div><p class="text-sm font-bold text-white">{{ tenantStore.name || 'Plataforma de Cursos' }}</p><p class="mt-0.5 text-[10px] font-semibold uppercase tracking-[.18em] text-white/45">Learning platform</p></div>
        </div>
        <div class="max-w-xl">
          <p class="text-xs font-bold uppercase tracking-[.2em] text-white/50">Capacitação profissional</p>
          <h1 class="mt-4 text-3xl font-bold leading-tight tracking-tight text-white xl:text-4xl">Aprender, acompanhar e certificar em uma experiência única.</h1>
          <p class="mt-4 max-w-lg text-sm leading-7 text-white/65">Treinamentos, progresso e certificados verificáveis com a identidade da sua organização.</p>
          <div class="mt-8 flex gap-3"><span class="rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/70 backdrop-blur">White-label</span><span class="rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/70 backdrop-blur">Certificação digital</span><span class="rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/70 backdrop-blur">B2B + B2C</span></div>
        </div>
        <p class="text-xs text-white/35">Ambiente seguro e personalizado para cada tenant.</p>
      </div>
    </section>

    <section class="relative flex min-h-screen flex-col overflow-hidden bg-[var(--surface-page)]" data-testid="auth-form-panel">
      <div class="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-[var(--brand-primary-soft)] blur-3xl"></div>
      <header class="relative px-6 pt-7 sm:px-10 lg:px-12">
        <router-link to="/" class="inline-flex items-center gap-3" data-testid="auth-brand">
          <div v-if="tenantStore.logo_url" class="flex h-10 min-w-10 items-center justify-center rounded-xl bg-white p-1.5 shadow-sm ring-1 ring-slate-100"><img :src="tenantStore.logo_url" :alt="tenantStore.name" class="max-h-7 max-w-[150px] object-contain" /></div>
          <span v-else-if="tenantStore.loading && !tenantStore.loaded" class="text-sm text-slate-400" data-testid="auth-brand-loading">Carregando…</span>
          <span v-else class="text-base font-bold text-slate-900">{{ tenantStore.name || 'Plataforma de Cursos' }}</span>
        </router-link>
      </header>
      <div class="relative flex flex-1 items-center justify-center px-6 py-10 sm:px-10 lg:px-12">
        <div class="w-full max-w-md" data-testid="auth-form-content"><slot /></div>
      </div>
      <footer class="relative px-6 py-5 text-center text-[11px] text-slate-400">&copy; {{ new Date().getFullYear() }} {{ tenantStore.name || 'Plataforma de Cursos' }}. Todos os direitos reservados.</footer>
    </section>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { useTenantStore } from '../stores/tenant'
import { getWrAuthVisual } from '../utils/courseMedia'
const tenantStore = useTenantStore()
const authVisual = computed(() => getWrAuthVisual())
const initials = computed(() => (tenantStore.name || 'PL').split(/\s+/).slice(0,2).map(p => p[0]).join('').toUpperCase())
const gradientStyle = computed(() => ({ background: `linear-gradient(145deg, ${tenantStore.secondary_color || '#17324D'} 0%, ${tenantStore.primary_color || '#1B7A3A'} 72%, ${tenantStore.accent_color || '#F59E0B'} 140%)` }))
</script>
