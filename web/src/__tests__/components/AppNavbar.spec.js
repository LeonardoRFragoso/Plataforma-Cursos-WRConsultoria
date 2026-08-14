import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppNavbar from '../../components/AppNavbar.vue'

const setupRouter = () => {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>home</div>' } },
      { path: '/dashboard', component: { template: '<div>dashboard</div>' } },
      { path: '/catalog', component: { template: '<div>catalog</div>' } },
      { path: '/courses', component: { template: '<div>courses</div>' } },
      { path: '/classes', component: { template: '<div>classes</div>' } },
      { path: '/students', component: { template: '<div>students</div>' } },
      { path: '/enrollments', component: { template: '<div>enrollments</div>' } },
      { path: '/payments', component: { template: '<div>payments</div>' } },
      { path: '/certificates', component: { template: '<div>certificates</div>' } },
      { path: '/login', component: { template: '<div>login</div>' } },
    ],
  })
}

describe('AppNavbar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders visitor menu', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    const router = setupRouter()
    await router.push('/')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Início')
    expect(wrapper.text()).toContain('Cursos')
    expect(wrapper.text()).toContain('Entrar')
  })

  it('renders admin menu', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
    auth.user = { full_name: 'Admin' }

    const router = setupRouter()
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Cursos')
    expect(wrapper.text()).toContain('Turmas')
    expect(wrapper.text()).toContain('Alunos')
    expect(wrapper.text()).toContain('Matrículas')
    expect(wrapper.text()).toContain('Pagamentos')
    expect(wrapper.text()).toContain('Certificados')
    expect(wrapper.text()).toContain('Sair')
  })

  it('renders student menu', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { full_name: 'Aluno' }

    const router = setupRouter()
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Explorar cursos')
    expect(wrapper.text()).toContain('Certificados')
    expect(wrapper.text()).toContain('Sair')
    expect(wrapper.text()).not.toContain('Cursos')
  })

  it('toggles mobile menu', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    const router = setupRouter()
    await router.push('/')
    await router.isReady()

    const wrapper = mount(AppNavbar, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('#mobile-menu').exists()).toBe(false)
    const toggle = wrapper.find('button[aria-label="Abrir ou fechar menu"]')
    await toggle.trigger('click')
    expect(wrapper.find('#mobile-menu').exists()).toBe(true)
  })
})
