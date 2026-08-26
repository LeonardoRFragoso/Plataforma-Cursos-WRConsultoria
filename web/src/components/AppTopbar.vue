<template>
  <header class="sticky top-0 z-20 border-b border-slate-200/70 bg-white/85 backdrop-blur-xl" data-testid="app-topbar">
    <div class="flex h-[76px] items-center justify-between gap-4 px-4 md:px-6 lg:px-8">
      <div class="flex min-w-0 items-center gap-3">
        <button type="button" class="md:hidden inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm hover:text-primary-600" :aria-expanded="open ? 'true' : 'false'" aria-controls="app-sidebar" aria-label="Abrir menu de navegação" data-testid="mobile-menu-toggle" @click="$emit('toggle-drawer')">
          <svg v-if="!open" class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" d="M4 7h16M4 12h16M4 17h16" /></svg>
          <svg v-else class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" d="m6 6 12 12M18 6 6 18" /></svg>
        </button>
        <div class="min-w-0">
          <div class="mb-0.5 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.14em] text-slate-400"><span>{{ sectionLabel }}</span><span class="h-1 w-1 rounded-full bg-slate-300"></span><span class="truncate">{{ tenantStore.name || 'Plataforma' }}</span></div>
          <p v-if="tenantStore.loading && !tenantStore.loaded" class="truncate text-sm text-slate-400" data-testid="topbar-brand-loading">Carregando…</p>
          <p v-else class="premium-title truncate text-base font-bold sm:text-lg">{{ currentpageTitle }}</p>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-2 sm:gap-3">
        <router-link v-if="quickAction" :to="quickAction.to" class="hidden lg:inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50"><NavIcon :name="quickAction.icon" />{{ quickAction.label }}</router-link>
        <div class="hidden sm:block text-right"><p class="max-w-[170px] truncate text-xs font-semibold text-slate-800">{{ authStore.user?.full_name || authStore.user?.email || '—' }}</p><p class="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-slate-400">{{ roleLabel }}</p></div>
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-black text-white shadow-md ring-4 ring-white" :style="avatarStyle" :title="authStore.user?.full_name || ''">{{ initials }}</div>
        <button type="button" @click="handleLogout" class="hidden rounded-xl px-3 py-2 text-xs font-semibold text-slate-500 transition hover:bg-red-50 hover:text-red-600 sm:inline-flex" data-testid="topbar-logout">Sair</button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import NavIcon from './NavIcon.vue'
defineProps({ open: { type: Boolean, default: false } }); defineEmits(['toggle-drawer'])
const route = useRoute(); const router = useRouter(); const authStore = useAuthStore(); const tenantStore = useTenantStore()
const roleMap = { admin: 'Administrador', student: 'Aluno', super_admin: 'Super Administrador' }
const roleLabel = computed(() => roleMap[authStore.userRole?.toLowerCase()] || authStore.userRole || '—')
const PAGE_TITLES = { '/dashboard':'Dashboard','/operations':'Central operacional','/operations/corporate':'Corporativo B2B','/operations/finance':'Reconciliação financeira','/operations/certificates':'Certificados confiáveis','/cursos':'Catálogo','/certificates':'Meus Certificados','/courses':'Cursos','/classes':'Turmas','/companies':'Empresas','/students':'Alunos','/enrollments':'Matrículas','/payments':'Pagamentos','/settings/white-label':'White Label','/settings/financial':'Configuração financeira','/super-admin':'Gestão Global' }
const currentpageTitle = computed(() => { const path = route.path; if (PAGE_TITLES[path]) return PAGE_TITLES[path]; for (const key of Object.keys(PAGE_TITLES).sort((a,b)=>b.length-a.length)) if (path.startsWith(key + '/')) return PAGE_TITLES[key]; return tenantStore.name || 'Plataforma' })
const sectionLabel = computed(() => route.path.startsWith('/operations') ? 'Operações' : route.path.startsWith('/settings') ? 'Configurações' : authStore.userRole?.toLowerCase() === 'student' ? 'Área do aluno' : 'Gestão')
const quickAction = computed(() => { const role = authStore.userRole?.toLowerCase(); if (role === 'admin' && !route.path.startsWith('/operations')) return { to:'/operations', label:'Ver operações', icon:'pulse' }; if (role === 'student' && route.path !== '/cursos') return { to:'/cursos', label:'Explorar catálogo', icon:'catalog' }; return null })
const initials = computed(() => { const name = authStore.user?.full_name || ''; if (!name) return '?'; const parts = name.trim().split(/\s+/); return parts.length === 1 ? parts[0].slice(0,2).toUpperCase() : (parts[0][0] + parts.at(-1)[0]).toUpperCase() })
const avatarStyle = computed(() => ({ background: `linear-gradient(135deg, ${tenantStore.primary_color || '#1B7A3A'}, ${tenantStore.secondary_color || '#17324D'})` }))
const handleLogout = () => { authStore.logout(); router.push('/login') }
</script>
