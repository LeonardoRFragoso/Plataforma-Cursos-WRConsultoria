import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import NotFound from '../../views/NotFound.vue'
import Forbidden from '../../views/Forbidden.vue'

describe('NotFound View', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>home</div>' } },
        { path: '/dashboard', component: { template: '<div>dashboard</div>' } },
        { path: '/super-admin', component: { template: '<div>super</div>' } },
        { path: '/:pathMatch(.*)*', name: 'NotFound', component: NotFound },
      ],
    })
  })

  it('links to / when not authenticated', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/nonexistent')
    await router.isReady()

    const wrapper = mount(NotFound, { global: { plugins: [router] } })
    const link = wrapper.find('[data-testid="notfound-home-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/')
  })

  it('links to /dashboard when authenticated as student', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/nonexistent')
    await router.isReady()

    const wrapper = mount(NotFound, { global: { plugins: [router] } })
    const link = wrapper.find('[data-testid="notfound-home-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/dashboard')
  })

  it('links to /super-admin when authenticated as super_admin', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'super_admin'
    auth.user = { role: 'super_admin' }

    await router.push('/nonexistent')
    await router.isReady()

    const wrapper = mount(NotFound, { global: { plugins: [router] } })
    const link = wrapper.find('[data-testid="notfound-home-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/super-admin')
  })
})

describe('Forbidden View', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>home</div>' } },
        { path: '/dashboard', component: { template: '<div>dashboard</div>' } },
        { path: '/super-admin', component: { template: '<div>super</div>' } },
        { path: '/403', name: 'Forbidden', component: Forbidden },
      ],
    })
  })

  it('renders 403 and role-aware home link for student', async () => {
    const auth = useAuthStore()
    auth.token = 'tok'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/403')
    await router.isReady()

    const wrapper = mount(Forbidden, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('403')
    expect(wrapper.text()).toContain('Acesso negado')
    const link = wrapper.find('[data-testid="forbidden-home-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/dashboard')
  })

  it('links to / when not authenticated', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/403')
    await router.isReady()

    const wrapper = mount(Forbidden, { global: { plugins: [router] } })
    const link = wrapper.find('[data-testid="forbidden-home-link"]')
    expect(link.attributes('href')).toBe('/')
  })
})
