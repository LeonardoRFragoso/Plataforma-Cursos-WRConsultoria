<template>
  <div>
    <!-- Mobile backdrop -->
    <div
      v-if="open"
      class="fixed inset-0 bg-black/50 z-30 md:hidden"
      data-testid="app-drawer-backdrop"
      @click="$emit('close')"
    ></div>

    <!-- Sidebar (persistent on desktop, drawer on mobile) -->
    <aside
      ref="sidebarRef"
      class="fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 flex flex-col transition-transform duration-200 ease-in-out md:translate-x-0"
      :class="open ? 'translate-x-0' : '-translate-x-full'"
      data-testid="app-sidebar"
      :aria-hidden="open ? 'false' : 'true'"
      aria-label="Navegação principal"
    >
      <!-- Branding -->
      <div class="h-16 flex items-center gap-2 px-4 border-b border-gray-200 shrink-0">
        <router-link :to="homeRoute" class="flex items-center min-w-0" data-testid="navbar-logo" @click="$emit('close')">
          <img
            v-if="tenantStore.logo_url"
            :src="tenantStore.logo_url"
            :alt="tenantStore.name"
            class="h-9 w-auto max-w-[140px] object-contain"
          />
          <span v-else class="text-lg font-bold text-primary-600 truncate">{{ tenantStore.name || 'Plataforma' }}</span>
        </router-link>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-1" aria-label="Navegação da conta">
        <!-- Flat links -->
        <router-link
          v-for="link in navItems.flat"
          :key="link.to"
          :to="link.to"
          :class="[
            'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
            isActive(link.to)
              ? 'bg-primary-50 text-primary-700'
              : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50',
          ]"
          :data-testid="'nav-link-' + link.testid"
          :aria-current="isActive(link.to) ? 'page' : undefined"
          @click="$emit('close')"
        >
          {{ link.label }}
        </router-link>

        <!-- Collapsible groups -->
        <div v-for="group in navItems.groups" :key="group.testid" class="pt-3">
          <button
            type="button"
            @click="toggleGroup(group.testid)"
            :class="[
              'w-full flex items-center justify-between rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-wide transition-colors',
              isGroupActive(group)
                ? 'text-primary-700'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50',
            ]"
            :data-testid="'nav-group-' + group.testid"
            :aria-expanded="isGroupOpen(group.testid) ? 'true' : 'false'"
            :aria-controls="'nav-group-panel-' + group.testid"
          >
            <span>{{ group.label }}</span>
            <svg
              class="h-4 w-4 transition-transform"
              :class="isGroupOpen(group.testid) ? 'rotate-180' : ''"
              fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"
            >
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div
            v-show="isGroupOpen(group.testid)"
            :id="'nav-group-panel-' + group.testid"
            :data-testid="'nav-group-panel-' + group.testid"
            class="mt-1 ml-2 space-y-1 border-l border-gray-200 pl-2"
          >
            <router-link
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              :class="[
                'block rounded-md px-3 py-2 text-sm transition-colors',
                isActive(item.to)
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50',
              ]"
              :data-testid="'nav-link-' + item.testid"
              :aria-current="isActive(item.to) ? 'page' : undefined"
              @click="$emit('close')"
            >
              {{ item.label }}
            </router-link>
          </div>
        </div>
      </nav>

      <!-- User / logout -->
      <div class="border-t border-gray-200 p-3 shrink-0">
        <div class="px-3 pb-2 text-xs text-gray-500 truncate">
          {{ authStore.user?.full_name || authStore.user?.email }}
        </div>
        <button
          type="button"
          @click="handleLogout"
          class="w-full text-left rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:text-red-600 hover:bg-gray-50 transition-colors"
          data-testid="nav-logout"
        >
          Sair
        </button>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import { useNavConfig } from '../composables/useNavConfig'
import { getHomeRoute } from '../utils/homeRoute'

const props = defineProps({
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const tenantStore = useTenantStore()
const { navItems } = useNavConfig()

const homeRoute = getHomeRoute(authStore)

const sidebarRef = ref(null)
const openGroups = ref(new Set())

const isActive = (path) => {
  if (route.path === path) return true
  if (route.path.startsWith(path + '/')) return true
  return false
}

const isGroupActive = (group) => group.items.some((item) => isActive(item.to))

const isGroupOpen = (testid) => openGroups.value.has(testid)

const toggleGroup = (testid) => {
  const next = new Set(openGroups.value)
  if (next.has(testid)) next.delete(testid)
  else next.add(testid)
  openGroups.value = next
}

// Open groups that contain the active route by default.
const initOpenGroups = () => {
  for (const group of navItems.value.groups) {
    if (group.items.some((item) => isActive(item.to))) {
      openGroups.value.add(group.testid)
    }
  }
}
initOpenGroups()

const handleLogout = () => {
  emit('close')
  authStore.logout()
  router.push('/login')
}

// Close drawer on route change.
watch(
  () => route.path,
  () => {
    emit('close')
  }
)

// Focus management + body scroll lock for the mobile drawer.
watch(
  () => props.open,
  async (opened) => {
    if (typeof document === 'undefined') return
    if (opened) {
      document.body.style.overflow = 'hidden'
      await nextTick()
      const firstLink = sidebarRef.value?.querySelector('a, button')
      firstLink?.focus()
    } else {
      document.body.style.overflow = ''
    }
  }
)
</script>
