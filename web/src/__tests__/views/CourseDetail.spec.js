import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { createRouter, createMemoryHistory } from 'vue-router'
import CourseDetail from '../../views/CourseDetail.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../../api/client'

const COURSE = {
  id: 'course-1',
  name: 'Curso Detalhe',
  category: 'Segurança',
  description: 'Descrição',
  carga_horaria: 40,
  modality: 'EAD',
  type: 'FORMACAO',
  code: 'NR-DET',
  price: 500,
}

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/courses/:id', name: 'CourseDetail', component: CourseDetail },
      { path: '/courses/:id/learn', name: 'CourseLearn', component: { template: '<div>learn</div>' } },
      { path: '/login', name: 'Login', component: { template: '<div>login</div>' } },
      { path: '/register', name: 'Register', component: { template: '<div>register</div>' } },
    ],
  })
}

async function mountDetail(enrollments = []) {
  const router = buildRouter()
  await router.push('/courses/course-1')
  await router.isReady()

  api.get.mockImplementation((url) => {
    if (url.includes('/enrollments/me')) {
      return Promise.resolve({ data: enrollments })
    }
    if (url.includes('/courses/')) {
      return Promise.resolve({ data: COURSE })
    }
    return Promise.resolve({ data: {} })
  })

  const wrapper = mount(CourseDetail, {
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

describe('CourseDetail View - acesso ao curso', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    vi.clearAllMocks()
  })

  it('mostra "Acessar curso" para matrícula CONFIRMADA', async () => {
    const wrapper = await mountDetail([
      { id: 'e1', course_id: 'course-1', status: 'CONFIRMADA' },
    ])
    const link = wrapper.find('a[href="/courses/course-1/learn"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('Acessar curso')
    // Não inicia nova compra automaticamente
    expect(wrapper.text()).not.toContain('Comprar novamente')
  })

  it('mostra "Acessar curso" para matrícula CONCLUIDA (não "Comprar novamente")', async () => {
    const wrapper = await mountDetail([
      { id: 'e1', course_id: 'course-1', status: 'CONCLUIDA' },
    ])
    const link = wrapper.find('a[href="/courses/course-1/learn"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('Acessar curso')
    expect(wrapper.text()).not.toContain('Comprar novamente')
  })

  it('mostra "Finalizar pagamento" para matrícula PENDENTE', async () => {
    const wrapper = await mountDetail([
      { id: 'e1', course_id: 'course-1', status: 'PENDENTE' },
    ])
    expect(wrapper.text()).toContain('Finalizar pagamento')
    expect(wrapper.find('a[href="/courses/course-1/learn"]').exists()).toBe(false)
  })

  it('mostra "Comprar novamente" apenas para matrícula CANCELADA', async () => {
    const wrapper = await mountDetail([
      { id: 'e1', course_id: 'course-1', status: 'CANCELADA' },
    ])
    expect(wrapper.text()).toContain('Comprar novamente')
    expect(wrapper.find('a[href="/courses/course-1/learn"]').exists()).toBe(false)
  })
})
