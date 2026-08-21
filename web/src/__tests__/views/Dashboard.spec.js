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

vi.mock('../../api/certificates', () => ({
  fetchMyCertificates: vi.fn(() => Promise.resolve({ data: [] })),
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
      { path: '/courses/:id/learn', component: { template: '<div></div>' } },
      { path: '/cursos', component: { template: '<div></div>' } },
      { path: '/certificates', component: { template: '<div></div>' } },
      { path: '/:pathMatch(.*)*', component: { template: '<div></div>' } },
    ],
  })
}

// Resolve the href rendered by a CourseProgressCard CTA (router-link) given the
// course id. The Dashboard delegates player links to CourseProgressCard, which
// stamps each CTA with data-testid="progress-card[-pending]-{courseId}-cta".
const ctaHref = (wrapper, courseId) => {
  const sel = `[data-testid="progress-card-${courseId}-cta"], [data-testid="progress-card-pending-${courseId}-cta"]`
  return wrapper.find(sel).attributes('href')
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

    // The redesigned student dashboard leads with "Continue aprendendo".
    expect(wrapper.text()).toContain('Continue aprendendo')
    expect(wrapper.text()).toContain('Curso de Teste')
    expect(wrapper.text()).toContain('Curso Confirmado')
    // PENDENTE is conveyed via a waiting hint rather than a raw status string.
    expect(wrapper.text()).toContain('Aguardando confirmação da matrícula')
    // CONFIRMADA is playable and offers a "Continuar curso" CTA.
    expect(wrapper.text()).toContain('Continuar curso')
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

    expect(wrapper.text()).toContain('Você ainda não está matriculado em nenhum curso.')
    expect(wrapper.text()).toContain('Explorar catálogo')
  })

  it('links to player for CONFIRMADA and CONCLUIDA', async () => {
    api.get.mockResolvedValue({
      data: [
        { ...baseEnrollment, id: 'e1', course_id: 'c1', course_name: 'Curso Confirmado', status: 'CONFIRMADA' },
        { ...baseEnrollment, id: 'e2', course_id: 'c2', course_name: 'Curso Concluído', status: 'CONCLUIDA' },
      ],
    })

    const router = setupRouter()
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(Dashboard, {
      global: { plugins: [pinia, router] },
    })
    await flushPromises()

    // Both playable enrollments must link to their respective learn routes.
    expect(ctaHref(wrapper, 'c1')).toContain('/courses/c1/learn')
    expect(ctaHref(wrapper, 'c2')).toContain('/courses/c2/learn')
  })

  it('does not link to player for PENDENTE and shows waiting message', async () => {
    api.get.mockResolvedValue({
      data: [{ ...baseEnrollment, status: 'PENDENTE' }],
    })

    const router = setupRouter()
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(Dashboard, {
      global: { plugins: [pinia, router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Aguardando confirmação da matrícula')
    // PENDENTE is not playable; CTA must route to the catalog, not the player.
    expect(ctaHref(wrapper, 'c1')).toContain('/cursos')
    expect(ctaHref(wrapper, 'c1')).not.toContain('/learn')
  })

  it('does not link to player for CANCELADA and routes to catalog', async () => {
    api.get.mockResolvedValue({
      data: [{ ...baseEnrollment, status: 'CANCELADA' }],
    })

    const router = setupRouter()
    await router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(Dashboard, {
      global: { plugins: [pinia, router] },
    })
    await flushPromises()

    // CANCELADA is not playable; CTA must route to the catalog, not the player.
    expect(ctaHref(wrapper, 'c1')).toContain('/cursos')
    expect(ctaHref(wrapper, 'c1')).not.toContain('/learn')
  })
})
