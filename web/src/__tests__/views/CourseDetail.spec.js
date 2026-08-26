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

const FREE_COURSE = {
  ...COURSE,
  name: 'Curso Gratuito',
  code: 'FREE-01',
  price: 0,
}

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/dashboard', component: { template: '<div></div>' } },
      { path: '/courses/:id', name: 'CourseDetail', component: CourseDetail },
      { path: '/courses/:id/learn', name: 'CourseLearn', component: { template: '<div>learn</div>' } },
      { path: '/cursos', component: { template: '<div></div>' } },
      { path: '/cursos/:id', component: { template: '<div></div>' } },
      { path: '/certificates', component: { template: '<div></div>' } },
      { path: '/validar-certificado', component: { template: '<div></div>' } },
      { path: '/seja-parceiro', component: { template: '<div></div>' } },
      { path: '/login', name: 'Login', component: { template: '<div>login</div>' } },
      { path: '/register', name: 'Register', component: { template: '<div>register</div>' } },
      { path: '/:pathMatch(.*)*', component: { template: '<div></div>' } },
    ],
  })
}

async function mountDetail(enrollments = [], selectedCourse = COURSE) {
  const router = buildRouter()
  await router.push('/courses/course-1')
  await router.isReady()

  api.get.mockImplementation((url) => {
    if (url.includes('/enrollments/me')) {
      return Promise.resolve({ data: enrollments })
    }
    if (url.includes('/courses/')) {
      return Promise.resolve({ data: selectedCourse })
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

  it('curso gratuito libera acesso sem criar checkout', async () => {
    const wrapper = await mountDetail([], FREE_COURSE)
    api.post.mockResolvedValueOnce({
      data: {
        enrollment: { id: 'free-enrollment', status: 'CONFIRMADA' },
        payment: null,
      },
    })

    expect(wrapper.text()).toContain('Começar curso grátis')
    expect(wrapper.text()).toContain('Acesso liberado sem pagamento')

    const freeButton = wrapper.findAll('button').find((button) => (
      button.text().includes('Começar curso grátis')
    ))
    expect(freeButton).toBeDefined()

    await freeButton.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/api/v1/enrollments/purchase', {
      course_id: 'course-1',
      method: 'UNDEFINED',
    })
    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/courses/course-1/learn')
  })
})

describe('CourseDetail View - CTAs anônimos preservam redirect', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null
    auth.initialized = true
    vi.clearAllMocks()
  })

  async function mountAnonymous() {
    const router = buildRouter()
    await router.push('/courses/course-1')
    await router.isReady()

    api.get.mockImplementation((url) => {
      if (url.includes('/enrollments/me')) return Promise.resolve({ data: [] })
      if (url.includes('/courses/')) return Promise.resolve({ data: COURSE })
      return Promise.resolve({ data: {} })
    })

    const wrapper = mount(CourseDetail, { global: { plugins: [router] } })
    await flushPromises()
    return { wrapper, router }
  }

  it('"Entrar para comprar" preserva caminho do curso', async () => {
    const { wrapper, router } = await mountAnonymous()

    const buttons = wrapper.findAll('button')
    const buyButton = buttons.find((b) => b.text().includes('Entrar para comprar'))
    expect(buyButton).toBeDefined()

    await buyButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/courses/course-1')
  })

  it('link "Entre" preserva redirect do curso', async () => {
    const { wrapper } = await mountAnonymous()

    // Check the computed property that drives the router-link :to binding
    expect(wrapper.vm.loginWithRedirect).toEqual({
      path: '/login',
      query: { redirect: '/courses/course-1' },
    })
  })

  it('link "cadastre-se" preserva redirect do curso', async () => {
    const { wrapper } = await mountAnonymous()

    expect(wrapper.vm.registerWithRedirect).toEqual({
      path: '/register',
      query: { redirect: '/courses/course-1' },
    })
  })
})