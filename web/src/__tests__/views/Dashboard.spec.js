import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia, storeToRefs } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import api from '../../api/client'
import Dashboard from '../../views/Dashboard.vue'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn() },
}))

let pinia

const baseEnrollment = {
  id: 'e1',
  course_id: 'c1',
  course_name: 'Curso de Teste',
  class_id: 'cl1',
  start_date: '2026-08-01',
  end_date: '2026-09-01',
  enrollment_date: '2026-08-01T00:00:00',
}

const setupRouter = () => {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/dashboard', component: Dashboard },
      { path: '/courses', component: { template: '<div></div>' } },
      { path: '/courses/:id', component: { template: '<div></div>' } },
      { path: '/certificates', component: { template: '<div></div>' } },
      { path: '/:pathMatch(.*)*', component: { template: '<div></div>' } },
    ],
  })
}

describe('Dashboard', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    const { userRole, user } = storeToRefs(authStore)
    userRole.value = 'student'
    user.value = { id: '1', full_name: 'Aluno', role: 'student' }
    api.get.mockReset()
  })

  it('renders student courses with status badges', async () => {
    api.get.mockResolvedValue({
      data: [
        { ...baseEnrollment, status: 'PENDENTE' },
        {
          ...baseEnrollment,
          id: 'e2',
          course_name: 'Curso Confirmado',
          course_id: 'c2',
          status: 'CONFIRMADA',
        },
      ],
    })

    const router = setupRouter()
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(Dashboard, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Meus Cursos')
    expect(wrapper.text()).toContain('Curso de Teste')
    expect(wrapper.text()).toContain('Curso Confirmado')
    expect(wrapper.text()).toContain('PENDENTE')
    expect(wrapper.text()).toContain('CONFIRMADA')
    expect(api.get).toHaveBeenCalledWith('/api/v1/enrollments/me')
  })

  it('renders empty state when student has no enrollments', async () => {
    api.get.mockResolvedValue({ data: [] })

    const router = setupRouter()
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(Dashboard, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Você não está matriculado em nenhum curso ainda.')
    expect(wrapper.text()).toContain('Explorar cursos')
  })
})
