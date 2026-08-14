import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { createRouter, createMemoryHistory } from 'vue-router'
import Catalog from '../../views/Catalog.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

import api from '../../api/client'

describe('Catalog View', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    api.get.mockReset()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div></div>' } },
        { path: '/catalog', component: Catalog },
        { path: '/courses/:id', component: { template: '<div></div>' } },
        { path: '/courses/:id/learn', component: { template: '<div></div>' } },
      ],
    })
  })

  it('renders loading state', async () => {
    api.get.mockReturnValue(new Promise(() => {}))
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/catalog')
    await router.isReady()
    const wrapper = mount(Catalog, { global: { plugins: [router] } })

    expect(wrapper.text()).toContain('Carregando cursos')
  })

  it('renders empty state', async () => {
    api.get.mockResolvedValue({ data: [] })
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/catalog')
    await router.isReady()
    const wrapper = mount(Catalog, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Nenhum curso disponível no momento')
  })

  it('renders list of active courses', async () => {
    api.get.mockResolvedValue({
      data: [
        {
          id: 'c1',
          name: 'Curso NR-10',
          code: 'NR-10',
          category: 'NR',
          modality: 'PRESENCIAL',
          carga_horaria: 40,
          price: 299.9,
          description: 'Curso de eletricidade',
          is_active: true,
        },
      ],
    })
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/catalog')
    await router.isReady()
    const wrapper = mount(Catalog, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Curso NR-10')
    expect(wrapper.text()).toContain('Entrar para continuar')
  })

  it('shows Acessar curso for enrolled student', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/enrollments/me')) {
        return Promise.resolve({ data: [{ course_id: 'c1' }] })
      }
      return Promise.resolve({
        data: [
          {
            id: 'c1',
            name: 'Curso NR-10',
            code: 'NR-10',
            category: 'NR',
            modality: 'PRESENCIAL',
            carga_horaria: 40,
            price: 299.9,
            is_active: true,
          },
        ],
      })
    })
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/catalog')
    await router.isReady()
    const wrapper = mount(Catalog, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Acessar curso')
  })

  it('shows error message on failure', async () => {
    api.get.mockRejectedValue(new Error('network'))
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/catalog')
    await router.isReady()
    const wrapper = mount(Catalog, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Não foi possível carregar os cursos')
  })
})
