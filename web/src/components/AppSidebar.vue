<template>
  <div id="app-sidebar">
    <div v-if="open" class="fixed inset-0 z-30 bg-slate-950/50 backdrop-blur-sm md:hidden" data-testid="app-drawer-backdrop" @click="$emit('close')"></div>

    <aside
      ref="sidebarRef"
      class="fixed inset-y-0 left-0 z-40 flex w-64 flex-col overflow-hidden border-r border-white/5 text-white shadow-2xl transition-transform duration-200 ease-in-out md:translate-x-0"
      :class="open ? 'translate-x-0' : '-translate-x-full'"
      data-testid="app-sidebar"
      :aria-hidden="drawerHidden ? 'true' : 'false'"
      :inert="drawerHidden ? '' : null"
      aria-label="Navegação principal"
    >
      <div class="absolute inset-0 bg-slate-950"></div>
      <div class="absolute inset-0 opacity-95" :style="sidebarBrandStyle"></div>
      <div class="absolute -left-20 top-16 h-60 w-60 rounded-full bg-white/5 blur-3xl"></div>

      <div class="relative flex h-[76px] shrink-0 items-center border-b border-white/10 px-5">
        <router-link :to="homeRoute" class="flex min-w-0 items-center gap-3" data-testid="navbar-logo" :title="tenantStore.name || ''" @click="$emit('close')">
          <div v-if="tenantStore.logo_white_url || tenantStore.logo_url" class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 p-1.5 ring-1 ring-white/10">
            <img :src="tenantStore.logo_white_url || tenantStore.logo_url" :alt="tenantStore.name" class="max-h-7 max-w-8 object-contain" />
          </div>
          <div v-else class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-sm font-black ring-1 ring-white/10">{{ brandInitials }}</div>
          <div class="min-w-0">
            <span v-if="tenantStore.loading && !tenantStore.loaded" class="block text-xs text-white/50" data-testid="sidebar-brand-loading">Carregando…</span>
            <template v-else>
              <span class="block truncate text-sm font-bold tracking-tight">{{ tenantStore.name || 'Plataforma' }}</span>
              <span class="mt-0.5 block truncate text-[10px] font-medium uppercase tracking-[.18em] text-white/45">Learning platform</span>
            </template>
          </div>
        </router-link>
      </div>

      <nav class="relative flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Navegação da conta">
        <router-link
          v-for="link in navItems.flat" :key="link.to" :to="link.to"
          :class="['group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all', isActive(link.to) ? 'bg-white text-[var(--brand-primary)] shadow-lg shadow-slate-950/10' : 'text-white/70 hover:bg-white/10 hover:text-white']"
          :data-testid="'nav-link-' + link.testid" :aria-current="isActive(link.to) ? 'page' : undefined" @click="$emit('close')"
        >
          <span :class="['flex h-8 w-8 items-center justify-center rounded-lg transition-colors', isActive(link.to) ? 'bg-[var(--brand-primary-soft)] text-[var(--brand-primary)]' : 'bg-white/5 text-white/65 group-hover:bg-white/10 group-hover:text-white']"><NavIcon :name="link.icon || 'home'" /></span>
          <span class="min-w-0 truncate">{{ link.label }}</span>
        </router-link>

        <div v-for="group in navItems.groups" :key="group.testid" class="pt-4">
          <button type="button" @click="toggleGroup(group.testid)"
            :class="['w-full flex items-center justify-between rounded-lg px-3 py-2 text-[10px] font-bold uppercase tracking-[.16em] transition-colors', isGroupActive(group) ? 'text-white' : 'text-white/40 hover:text-white/65']"
            :data-testid="'nav-group-' + group.testid" :aria-expanded="isGroupOpen(group.testid) ? 'true' : 'false'" :aria-controls="'nav-group-panel-' + group.testid">
            <span class="flex items-center gap-2"><NavIcon v-if="group.icon" :name="group.icon" class="h-4 w-4" />{{ group.label }}</span>
            <svg class="h-3.5 w-3.5 transition-transform" :class="isGroupOpen(group.testid) ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m6 9 6 6 6-6" /></svg>
          </button>
          <div v-show="isGroupOpen(group.testid)" :id="'nav-group-panel-' + group.testid" :data-testid="'nav-group-panel-' + group.testid" class="mt-1 space-y-1">
            <router-link v-for="item in group.items" :key="item.to" :to="item.to"
              :class="['group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all', isActive(item.to) ? 'bg-white text-[var(--brand-primary)] font-semibold' : 'text-white/62 hover:bg-white/8 hover:text-white']"
              :data-testid="'nav-link-' + item.testid" :aria-current="isActive(item.to) ? 'page' : undefined" @click="$emit('close')">
              <span :class="['flex h-7 w-7 items-center justify-center rounded-lg', isActive(item.to) ? 'bg-[var(--brand-primary-soft)] text-[var(--brand-primary)]' : 'text-white/45 group-hover:text-white/80']"><NavIcon :name="item.icon || 'arrow'" /></span>
              <span class="min-w-0 truncate">{{ item.label }}</span>
            </router-link>
          </div>
        </div>
      </nav>

      <div class="relative m-3 rounded-2xl border border-white/10 bg-white/[.07] p-3 backdrop-blur-sm">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-xs font-black text-slate-900">{{ userInitials }}</div>
          <div class="min-w-0 flex-1"><p class="truncate text-xs font-semibold text-white">{{ authStore.user?.full_name || authStore.user?.email }}</p><p class="mt-0.5 text-[10px] uppercase tracking-wider text-white/45">{{ roleLabel }}</p></div>
        </div>
        <button type="button" @click="handleLogout" class="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-white/65 transition hover:bg-white/10 hover:text-white" data-testid="nav-logout"><NavIcon name="logout" />Sair</button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import { useNavConfig } from '../composables/useNavConfig'
import { getHomeRoute } from '../utils/homeRoute'
import NavIcon from './NavIcon.vue'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])
const route = useRoute(); const router = useRouter(); const authStore = useAuthStore(); const tenantStore = useTenantStore(); const { navItems } = useNavConfig()
const homeRoute = getHomeRoute(authStore); const sidebarRef = ref(null); const openGroups = ref(new Set()); const isDesktop = ref(true)
const isActive = (path) => route.path === path || route.path.startsWith(path + '/')
const isGroupActive = (group) => group.items.some((item) => isActive(item.to))
const isGroupOpen = (testid) => openGroups.value.has(testid)
const toggleGroup = (testid) => { const next = new Set(openGroups.value); next.has(testid) ? next.delete(testid) : next.add(testid); openGroups.value = next }
const initOpenGroups = () => { for (const group of navItems.value.groups) if (group.items.some((item) => isActive(item.to))) openGroups.value.add(group.testid) }
initOpenGroups()
const drawerHidden = computed(() => !isDesktop.value && !props.open)
const syncViewport = () => { if (typeof window !== 'undefined') isDesktop.value = window.matchMedia('(min-width: 768px)').matches }
const brandInitials = computed(() => (tenantStore.name || 'PL').split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase())
const userInitials = computed(() => { const name = authStore.user?.full_name || authStore.user?.email || 'U'; const parts = name.trim().split(/\s+/); return ((parts[0]?.[0] || '') + (parts.length > 1 ? parts.at(-1)?.[0] || '' : parts[0]?.[1] || '')).toUpperCase() })
const roleLabel = computed(() => ({ admin: 'Administrador', student: 'Aluno', super_admin: 'Super Admin' }[authStore.userRole?.toLowerCase()] || authStore.userRole || 'Conta'))
const sidebarBrandStyle = computed(() => ({ background: `linear-gradient(165deg, ${tenantStore.primary_color || '#047F37'} 0%, color-mix(in srgb, ${tenantStore.primary_color || '#047F37'} 76%, #020617) 58%, #020617 100%)` }))
const handleLogout = () => { emit('close'); authStore.logout(); router.push('/login') }
watch(() => route.path, () => { emit('close'); initOpenGroups() })
watch(() => props.open, async (opened) => { if (typeof document === 'undefined') return; if (opened) { document.body.style.overflow = 'hidden'; await nextTick(); sidebarRef.value?.querySelector('a, button')?.focus() } else document.body.style.overflow = '' })
onMounted(() => { syncViewport(); window.addEventListener('resize', syncViewport) })
onBeforeUnmount(() => { if (typeof window !== 'undefined') window.removeEventListener('resize', syncViewport) })
</script>
