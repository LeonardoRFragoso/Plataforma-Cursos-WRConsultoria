import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import CourseProgress from '../../views/CourseProgress.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn((url) => {
      if (url.includes('/courses/') && !url.includes('/progress')) {
        return Promise.resolve({ data: { id: 'c1', name: 'NR-10 Segurança' } })
      }
      if (url.includes('/progress')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: [] })
    }),
  },
}))

import api from '../../api/client'

function setupRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/dashboard', component: { template: '<div></div>' } },
      { path: '/courses', component: { template: '<div></div>' } },
      { path: '/courses/:id', component: { template: '<div></div>' } },
      { path: '/courses/:id/progress', component: { template: '<div>progress</div>' } },
      { path: '/courses/:id/lessons', component: { template: '<div>lessons</div>' } },
      { path: '/cursos', component: { template: '<div></div>' } },
      { path: '/certificates', component: { template: '<div></div>' } },
      { path: '/validar-certificado', component: { template: '<div></div>' } },
      { path: '/seja-parceiro', component: { template: '<div></div>' } },
      { path: '/login', component: { template: '<div></div>' } },
      { path: '/register', component: { template: '<div></div>' } },
      { path: '/classes', component: { template: '<div></div>' } },
      { path: '/students', component: { template: '<div></div>' } },
      { path: '/enrollments', component: { template: '<div></div>' } },
      { path: '/payments', component: { template: '<div></div>' } },
      { path: '/settings/white-label', component: { template: '<div></div>' } },
      { path: '/super-admin', component: { template: '<div></div>' } },
      { path: '/:pathMatch(.*)*', component: { template: '<div></div>' } },
    ],
  })
}

async function mountView() {
  const router = setupRouter()
  await router.push('/courses/c1/progress')
  await router.isReady()
  return mount(CourseProgress, { global: { plugins: [router] } })
}

describe('CourseProgress', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.get.mockReset()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows loading state initially', async () => {
    api.get.mockReturnValue(new Promise(() => {})) // never resolves
    const wrapper = await mountView()
    // Should show loading text
    expect(wrapper.text()).toContain('Carregando')
  })

  it('shows error state on API failure', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/progress')) return Promise.reject(new Error('fail'))
      return Promise.resolve({ data: { id: 'c1', name: 'Test' } })
    })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Não foi possível carregar')
    expect(wrapper.text()).toContain('Tentar novamente')
  })

  it('shows empty state when no students enrolled', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/progress')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: { id: 'c1', name: 'Test Course' } })
    })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Nenhum aluno matriculado')
  })

  it('shows progress table with student data', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/progress')) {
        return Promise.resolve({
          data: [
            {
              student_id: 's1',
              student_name: 'João Silva',
              class_name: 'Turma A',
              enrollment_status: 'CONFIRMADA',
              required_completed: 3,
              required_total: 4,
              percentage: 75,
              certificate_status: 'Não',
            },
          ],
        })
      }
      return Promise.resolve({ data: { id: 'c1', name: 'NR-10' } })
    })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('João Silva')
    expect(wrapper.text()).toContain('Turma A')
    expect(wrapper.text()).toContain('75%')
    expect(wrapper.text()).toContain('3 / 4')
  })

  it('shows translated status labels', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/progress')) {
        return Promise.resolve({
          data: [
            { student_id: 's1', student_name: 'A', class_name: 'C', enrollment_status: 'CONFIRMADA', required_completed: 1, required_total: 1, percentage: 100, certificate_status: 'Sim' },
            { student_id: 's2', student_name: 'B', class_name: 'C', enrollment_status: 'PENDENTE', required_completed: 0, required_total: 1, percentage: 0, certificate_status: 'Não' },
            { student_id: 's3', student_name: 'D', class_name: 'C', enrollment_status: 'CONCLUIDA', required_completed: 1, required_total: 1, percentage: 100, certificate_status: 'Sim' },
            { student_id: 's4', student_name: 'E', class_name: 'C', enrollment_status: 'CANCELADA', required_completed: 0, required_total: 1, percentage: 0, certificate_status: 'Não' },
          ],
        })
      }
      return Promise.resolve({ data: { id: 'c1', name: 'Test' } })
    })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Confirmada')
    expect(wrapper.text()).toContain('Pendente')
    expect(wrapper.text()).toContain('Concluída')
    expect(wrapper.text()).toContain('Cancelada')
    // Should NOT show raw English status
    expect(wrapper.text()).not.toContain('CONFIRMADA')
    expect(wrapper.text()).not.toContain('CANCELADA')
  })

  it('shows certificate status yes/no', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/progress')) {
        return Promise.resolve({
          data: [
            { student_id: 's1', student_name: 'With Cert', class_name: 'C', enrollment_status: 'CONCLUIDA', required_completed: 1, required_total: 1, percentage: 100, certificate_status: 'Sim' },
            { student_id: 's2', student_name: 'No Cert', class_name: 'C', enrollment_status: 'CONFIRMADA', required_completed: 0, required_total: 1, percentage: 0, certificate_status: 'Não' },
          ],
        })
      }
      return Promise.resolve({ data: { id: 'c1', name: 'Test' } })
    })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('Sim')
    expect(wrapper.text()).toContain('Não')
  })

  it('has back to lessons button', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/progress')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: { id: 'c1', name: 'Test' } })
    })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.find('[data-testid="back-to-lessons-btn"]').exists()).toBe(true)
  })

  it('displays course name in header', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/progress')) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: { id: 'c1', name: 'NR-10 Segurança Elétrica' } })
    })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('NR-10 Segurança Elétrica')
  })
})
