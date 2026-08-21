import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useTenantStore } from '../../stores/tenant'
import AppTopbar from '../../components/AppTopbar.vue'

function setup(role) {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.token = 'tok'
  auth.userRole = role
  auth.user = { id: 'u1', full_name: 'João Silva', email: 'joao@x.com', role }
  const tenant = useTenantStore()
  tenant.name = 'WR Consultoria'
  return { auth, tenant }
}

async function mountTopbar(role, open = false) {
  const ctx = setup(role)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div></div>' } }, { path: '/login', component: { template: '<div></div>' } }],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(AppTopbar, {
    global: { plugins: [router] },
    props: { open },
  })
  return { ...ctx, wrapper, router }
}

describe('AppTopbar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders tenant platform context', async () => {
    const { wrapper } = await mountTopbar('admin')
    expect(wrapper.find('[data-testid="app-topbar"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('WR Consultoria')
  })

  it('renders the mobile menu trigger with accessible name and aria-expanded', async () => {
    const { wrapper } = await mountTopbar('student', false)
    const toggle = wrapper.find('[data-testid="mobile-menu-toggle"]')
    expect(toggle.exists()).toBe(true)
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.attributes('aria-label')).toBeTruthy()
    expect(toggle.attributes('aria-controls')).toBe('app-sidebar')
    await wrapper.setProps({ open: true })
    expect(toggle.attributes('aria-expanded')).toBe('true')
  })

  it('emits toggle-drawer when the hamburger is clicked', async () => {
    const { wrapper } = await mountTopbar('student')
    await wrapper.find('[data-testid="mobile-menu-toggle"]').trigger('click')
    expect(wrapper.emitted('toggle-drawer')).toBeTruthy()
  })

  it('shows the role label and user name', async () => {
    const { wrapper } = await mountTopbar('admin')
    expect(wrapper.text()).toContain('Administrador')
    expect(wrapper.text()).toContain('João Silva')
  })

  it('logout clears auth and redirects to /login', async () => {
    const { wrapper, router, auth } = await mountTopbar('student')
    const pushSpy = vi.spyOn(router, 'push')
    await wrapper.find('[data-testid="topbar-logout"]').trigger('click')
    expect(auth.token).toBeNull()
    expect(pushSpy).toHaveBeenCalledWith('/login')
  })
})
