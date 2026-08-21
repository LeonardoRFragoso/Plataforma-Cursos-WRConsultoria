import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useTenantStore } from '../../stores/tenant'
import AuthenticatedLayout from '../../layouts/AuthenticatedLayout.vue'

function setup(role) {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.token = 'tok'
  auth.userRole = role
  auth.user = { id: 'u1', full_name: 'Admin User', email: 'a@x.com', role }
  const tenant = useTenantStore()
  tenant.name = 'WR Consultoria'
  tenant.logo_url = null
  return { auth, tenant }
}

async function mountShell(role = 'admin', initialPath = '/dashboard') {
  const ctx = setup(role)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/dashboard', component: { template: '<div></div>' } },
      { path: '/courses', component: { template: '<div></div>' } },
      { path: '/login', component: { template: '<div></div>' } },
    ],
  })
  await router.push(initialPath)
  await router.isReady()
  const wrapper = mount(AuthenticatedLayout, {
    global: { plugins: [router] },
    slots: { default: '<div data-testid="slot-content">workspace content</div>' },
  })
  return { ...ctx, wrapper, router }
}

describe('AuthenticatedLayout (AppShell)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the shell, sidebar, topbar and workspace markers', async () => {
    const { wrapper } = await mountShell()
    expect(wrapper.find('[data-testid="app-shell"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="app-sidebar"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="app-topbar"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="app-workspace"]').exists()).toBe(true)
  })

  it('renders slot content inside the workspace', async () => {
    const { wrapper } = await mountShell()
    expect(wrapper.find('[data-testid="slot-content"]').exists()).toBe(true)
  })

  it('workspace is full-width — no root max-w-7xl centered container', async () => {
    const { wrapper } = await mountShell()
    const workspace = wrapper.find('[data-testid="app-workspace"]')
    expect(workspace.exists()).toBe(true)
    // The workspace element itself must not carry a centered max-width class
    expect(workspace.classes().some((c) => c.startsWith('max-w-7xl'))).toBe(false)
    expect(workspace.classes()).not.toContain('mx-auto')
    expect(workspace.classes()).toContain('w-full')
  })

  it('main column is offset by the sidebar width on desktop (md:ml-64)', async () => {
    const { wrapper } = await mountShell()
    const offset = wrapper.find('.md\\:ml-64')
    expect(offset.exists()).toBe(true)
  })

  it('mobile drawer opens via topbar toggle and closes via sidebar close', async () => {
    const { wrapper } = await mountShell()
    // Drawer backdrop hidden initially
    expect(wrapper.find('[data-testid="app-drawer-backdrop"]').exists()).toBe(false)
    // Open via topbar hamburger
    await wrapper.find('[data-testid="mobile-menu-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="app-drawer-backdrop"]').exists()).toBe(true)
    // Close via backdrop click
    await wrapper.find('[data-testid="app-drawer-backdrop"]').trigger('click')
    expect(wrapper.find('[data-testid="app-drawer-backdrop"]').exists()).toBe(false)
  })

  it('does not render public-layout marker', async () => {
    const { wrapper } = await mountShell()
    expect(wrapper.find('[data-testid="public-layout"]').exists()).toBe(false)
  })
})
