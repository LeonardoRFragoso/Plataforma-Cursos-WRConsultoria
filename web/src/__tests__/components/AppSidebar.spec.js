import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useTenantStore } from '../../stores/tenant'
import AppSidebar from '../../components/AppSidebar.vue'

const routes = [
  { path: '/', component: { template: '<div></div>' } },
  { path: '/dashboard', component: { template: '<div></div>' } },
  { path: '/courses', component: { template: '<div></div>' } },
  { path: '/classes', component: { template: '<div></div>' } },
  { path: '/students', component: { template: '<div></div>' } },
  { path: '/enrollments', component: { template: '<div></div>' } },
  { path: '/payments', component: { template: '<div></div>' } },
  { path: '/certificates', component: { template: '<div></div>' } },
  { path: '/settings/white-label', component: { template: '<div></div>' } },
  { path: '/super-admin', component: { template: '<div></div>' } },
  { path: '/cursos', component: { template: '<div></div>' } },
  { path: '/login', component: { template: '<div></div>' } },
]

function setup(role) {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.token = 'tok'
  auth.userRole = role
  auth.user = { id: 'u1', full_name: 'Test User', email: 't@x.com', role }
  const tenant = useTenantStore()
  tenant.name = 'WR Consultoria'
  tenant.logo_url = null
  return { auth, tenant }
}

async function mountSidebar(role, initialPath = '/dashboard') {
  const ctx = setup(role)
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(initialPath)
  await router.isReady()
  const wrapper = mount(AppSidebar, {
    global: { plugins: [router] },
    props: { open: false },
  })
  return { ...ctx, wrapper, router }
}

describe('AppSidebar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders tenant branding (name fallback) and logo link', async () => {
    const { wrapper } = await mountSidebar('student')
    expect(wrapper.find('[data-testid="navbar-logo"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('WR Consultoria')
  })

  it('student nav: Dashboard, Catálogo, Certificados — no admin links', async () => {
    const { wrapper } = await mountSidebar('student')
    expect(wrapper.find('[data-testid="nav-link-dashboard"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-catalog"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-certificates"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-courses"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="nav-group-management"]').exists()).toBe(false)
  })

  it('admin nav: Dashboard + Gestão group with admin links', async () => {
    const { wrapper } = await mountSidebar('admin')
    expect(wrapper.find('[data-testid="nav-link-dashboard"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-group-management"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-courses"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-payments"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-super-admin"]').exists()).toBe(false)
  })

  it('super_admin nav: Gestão Global only — no tenant-admin groups', async () => {
    const { wrapper } = await mountSidebar('super_admin', '/super-admin')
    expect(wrapper.find('[data-testid="nav-link-super-admin"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-group-management"]').exists()).toBe(false)
  })

  it('marks the active route with aria-current="page"', async () => {
    const { wrapper } = await mountSidebar('student', '/dashboard')
    const dash = wrapper.find('[data-testid="nav-link-dashboard"]')
    expect(dash.attributes('aria-current')).toBe('page')
    const catalog = wrapper.find('[data-testid="nav-link-catalog"]')
    expect(catalog.attributes('aria-current')).toBeUndefined()
  })

  it('admin group toggle changes aria-expanded', async () => {
    const { wrapper } = await mountSidebar('admin')
    const group = wrapper.find('[data-testid="nav-group-management"]')
    // Active route /dashboard is not inside management group, so it starts closed
    expect(group.attributes('aria-expanded')).toBe('false')
    await group.trigger('click')
    expect(group.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('[data-testid="nav-group-panel-management"]').isVisible()).toBe(true)
  })

  it('opens the group containing the active route by default', async () => {
    const { wrapper } = await mountSidebar('admin', '/courses')
    const group = wrapper.find('[data-testid="nav-group-management"]')
    expect(group.attributes('aria-expanded')).toBe('true')
  })

  it('logout clears auth and redirects to /login', async () => {
    const { wrapper, router, auth } = await mountSidebar('student')
    const pushSpy = vi.spyOn(router, 'push')
    await wrapper.find('[data-testid="nav-logout"]').trigger('click')
    expect(auth.token).toBeNull()
    expect(pushSpy).toHaveBeenCalledWith('/login')
  })

  it('emits close when a nav link is clicked', async () => {
    const { wrapper } = await mountSidebar('student')
    await wrapper.find('[data-testid="nav-link-catalog"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('renders the mobile drawer backdrop when open', async () => {
    const { wrapper } = await mountSidebar('student')
    expect(wrapper.find('[data-testid="app-drawer-backdrop"]').exists()).toBe(false)
    await wrapper.setProps({ open: true })
    expect(wrapper.find('[data-testid="app-drawer-backdrop"]').exists()).toBe(true)
  })
})

describe('AppSidebar — WR brand sidebar background (tenant-based)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('WR + ADMIN: sidebar background uses tenant primary_color', async () => {
    const { wrapper, tenant } = await mountSidebar('admin')
    tenant.primary_color = '#047F37'
    await wrapper.vm.$nextTick()
    const bg = wrapper.vm.sidebarBrandStyle.background
    expect(bg).toContain('#047F37')
  })

  it('WR + STUDENT: sidebar background uses tenant primary_color', async () => {
    const { wrapper, tenant } = await mountSidebar('student')
    tenant.primary_color = '#047F37'
    await wrapper.vm.$nextTick()
    const bg = wrapper.vm.sidebarBrandStyle.background
    expect(bg).toContain('#047F37')
  })

  it('WR + SUPER_ADMIN: sidebar background uses tenant primary_color', async () => {
    const { wrapper, tenant } = await mountSidebar('super_admin', '/super-admin')
    tenant.primary_color = '#047F37'
    await wrapper.vm.$nextTick()
    const bg = wrapper.vm.sidebarBrandStyle.background
    expect(bg).toContain('#047F37')
  })

  it('non-WR tenant: sidebar does NOT use #047F37', async () => {
    const { wrapper, tenant } = await mountSidebar('admin')
    tenant.primary_color = '#E86A17' // Alfa orange
    await wrapper.vm.$nextTick()
    const bg = wrapper.vm.sidebarBrandStyle.background
    expect(bg).not.toContain('#047F37')
    expect(bg).toContain('#E86A17')
  })

  it('active nav item uses brand-primary text color (tenant-based)', async () => {
    const { wrapper } = await mountSidebar('student', '/dashboard')
    const activeLink = wrapper.find('[data-testid="nav-link-dashboard"]')
    expect(activeLink.classes()).toContain('text-[var(--brand-primary)]')
    expect(activeLink.classes()).not.toContain('text-slate-950')
  })
})
