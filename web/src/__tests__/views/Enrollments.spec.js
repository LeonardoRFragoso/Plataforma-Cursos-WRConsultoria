import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import Enrollments from '../../views/Enrollments.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

describe('Enrollments View', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/enrollments', component: Enrollments },
        { path: '/dashboard', component: { template: '<div>dash</div>' } },
        { path: '/courses', component: { template: '<div>courses</div>' } },
        { path: '/classes', component: { template: '<div>classes</div>' } },
        { path: '/students', component: { template: '<div>students</div>' } },
        { path: '/payments', component: { template: '<div>pay</div>' } },
        { path: '/certificates', component: { template: '<div>certs</div>' } },
        { path: '/settings/white-label', component: { template: '<div>wl</div>' } },
        { path: '/', component: { template: '<div>home</div>' } },
      ],
    })
  })

  it('renderiza a página de matrículas', async () => {
    await router.push('/enrollments')
    await router.isReady()
    const wrapper = mount(Enrollments, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Matrículas')
  })

  it('exibe botão de nova matrícula para admin', async () => {
    await router.push('/enrollments')
    await router.isReady()
    const wrapper = mount(Enrollments, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('+ Nova Matrícula')
  })

  it('mostra mensagem quando não há matrículas', async () => {
    await router.push('/enrollments')
    await router.isReady()
    const wrapper = mount(Enrollments, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Nenhuma matrícula cadastrada')
  })
})
