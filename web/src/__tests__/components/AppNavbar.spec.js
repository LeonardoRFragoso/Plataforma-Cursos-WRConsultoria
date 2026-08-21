import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import AppNavbar from '../../components/AppNavbar.vue'

describe('AppNavbar', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>home</div>' } },
        { path: '/dashboard', component: { template: '<div>dash</div>' } },
        { path: '/courses', component: { template: '<div>courses</div>' } },
        { path: '/classes', component: { template: '<div>classes</div>' } },
        { path: '/students', component: { template: '<div>students</div>' } },
        { path: '/enrollments', component: { template: '<div>enr</div>' } },
        { path: '/payments', component: { template: '<div>pay</div>' } },
        { path: '/certificates', component: { template: '<div>certs</div>' } },
        { path: '/settings/white-label', component: { template: '<div>wl</div>' } },
        { path: '/super-admin', component: { template: '<div>sa</div>' } },
        { path: '/login', component: { template: '<div>login</div>' } },
        { path: '/register', component: { template: '<div>reg</div>' } },
      ],
    })
  })

  it('logo links to / when not authenticated', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    const logo = wrapper.find('[data-testid="navbar-logo"]')
    expect(logo.exists()).toBe(true)
    expect(logo.attributes('href')).toBe('/')
  })

  it('logo links to /dashboard when authenticated as student', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    const logo = wrapper.find('[data-testid="navbar-logo"]')
    expect(logo.attributes('href')).toBe('/dashboard')
  })

  it('logo links to /super-admin when authenticated as super_admin', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'super_admin'
    auth.user = { role: 'super_admin' }

    await router.push('/super-admin')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    const logo = wrapper.find('[data-testid="navbar-logo"]')
    expect(logo.attributes('href')).toBe('/super-admin')
  })

  it('shows student nav links (Dashboard, Certificates)', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    expect(wrapper.find('[data-testid="nav-link-dashboard"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-certificates"]').exists()).toBe(true)
    // Student should NOT see admin-only links
    expect(wrapper.find('[data-testid="nav-link-courses"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="nav-link-classes"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="nav-link-super-admin"]').exists()).toBe(false)
  })

  it('shows admin nav with Dashboard flat + Gestão/Certificados/Personalização dropdown groups', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'admin'
    auth.user = { role: 'admin' }

    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    // Dashboard is a flat link
    expect(wrapper.find('[data-testid="nav-link-dashboard"]').exists()).toBe(true)
    // Management dropdown group exists
    expect(wrapper.find('[data-testid="nav-group-management"]').exists()).toBe(true)
    // Certificates dropdown group exists
    expect(wrapper.find('[data-testid="nav-group-certificates-group"]').exists()).toBe(true)
    // Customization dropdown group exists
    expect(wrapper.find('[data-testid="nav-group-customization"]').exists()).toBe(true)
    // Admin should NOT see super admin link
    expect(wrapper.find('[data-testid="nav-link-super-admin"]').exists()).toBe(false)
  })

  it('admin dropdown shows management links when opened', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'admin'
    auth.user = { role: 'admin' }

    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    // Dropdown items should not be visible initially
    expect(wrapper.find('[data-testid="dropdown-panel-management"]').exists()).toBe(false)

    // Open the management dropdown
    await wrapper.find('[data-testid="nav-group-management"]').trigger('click')
    expect(wrapper.find('[data-testid="dropdown-panel-management"]').exists()).toBe(true)
    // Now the management links should be visible
    expect(wrapper.find('[data-testid="nav-link-courses"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-classes"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-students"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-enrollments"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="nav-link-payments"]').exists()).toBe(true)
  })

  it('shows super_admin nav with Gestão Global only', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'super_admin'
    auth.user = { role: 'super_admin' }

    await router.push('/super-admin')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    expect(wrapper.find('[data-testid="nav-link-super-admin"]').exists()).toBe(true)
    // Super admin should NOT see admin dropdown groups
    expect(wrapper.find('[data-testid="nav-group-management"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="nav-group-customization"]').exists()).toBe(false)
  })

  it('shows login/register when not authenticated', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('Login')
    expect(wrapper.text()).toContain('Cadastre-se')
    expect(wrapper.find('[data-testid="nav-logout"]').exists()).toBe(false)
  })

  it('shows logout button when authenticated', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    expect(wrapper.find('[data-testid="nav-logout"]').exists()).toBe(true)
  })

  it('has mobile menu toggle when authenticated', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    expect(wrapper.find('[data-testid="mobile-menu-toggle"]').exists()).toBe(true)
  })

  it('mobile menu panel opens on toggle click', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    expect(wrapper.find('[data-testid="mobile-menu-panel"]').exists()).toBe(false)

    await wrapper.find('[data-testid="mobile-menu-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="mobile-menu-panel"]').exists()).toBe(true)
  })
})
