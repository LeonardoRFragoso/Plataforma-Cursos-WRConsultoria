import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { createRouter, createMemoryHistory } from 'vue-router'
import CourseDetail from '../../views/CourseDetail.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

import api from '../../api/client'

describe('CourseDetail View', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    api.get.mockReset()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div></div>' } },
        { path: '/courses/:id', component: CourseDetail },
        { path: '/courses/:id/learn', component: { template: '<div></div>' } },
        { path: '/catalog', component: { template: '<div></div>' } },
        { path: '/courses', component: { template: '<div></div>' } },
      ],
    })
  })

  it('renders course details for visitor', async () => {
    api.get.mockResolvedValue({
      data: {
        id: 'c1',
        name: 'Curso NR-10',
        code: 'NR-10',
        category: 'NR',
        modality: 'PRESENCIAL',
        carga_horaria: 40,
        price: 299.9,
        description: 'Descrição do curso',
        is_active: true,
      },
    })
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/courses/c1')
    await router.isReady()
    const wrapper = mount(CourseDetail, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Curso NR-10')
    expect(wrapper.text()).toContain('Entrar para continuar')
  })

  it('renders Acessar curso for enrolled student', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/enrollments/me')) {
        return Promise.resolve({ data: [{ course_id: 'c1' }] })
      }
      return Promise.resolve({
        data: {
          id: 'c1',
          name: 'Curso NR-10',
          code: 'NR-10',
          category: 'NR',
          modality: 'PRESENCIAL',
          carga_horaria: 40,
          price: 299.9,
          is_active: true,
        },
      })
    })
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/courses/c1')
    await router.isReady()
    const wrapper = mount(CourseDetail, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Acessar curso')
  })

  it('renders Gerenciar cursos for admin', async () => {
    api.get.mockResolvedValue({
      data: {
        id: 'c1',
        name: 'Curso NR-10',
        code: 'NR-10',
        category: 'NR',
        modality: 'PRESENCIAL',
        carga_horaria: 40,
        price: 299.9,
        is_active: true,
      },
    })
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
    auth.user = { role: 'admin' }

    await router.push('/courses/c1')
    await router.isReady()
    const wrapper = mount(CourseDetail, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Gerenciar cursos')
  })

  it('shows unavailable message for inactive course', async () => {
    api.get.mockResolvedValue({
      data: {
        id: 'c1',
        name: 'Curso NR-10',
        is_active: false,
      },
    })
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/courses/c1')
    await router.isReady()
    const wrapper = mount(CourseDetail, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Curso indisponível no momento')
  })

  it('shows error on api failure', async () => {
    api.get.mockRejectedValue(new Error('network'))
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null

    await router.push('/courses/c1')
    await router.isReady()
    const wrapper = mount(CourseDetail, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Não foi possível carregar o curso')
  })
})
