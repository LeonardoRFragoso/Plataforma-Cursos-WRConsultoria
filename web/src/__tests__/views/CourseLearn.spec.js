import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { createRouter, createMemoryHistory } from 'vue-router'
import CourseLearn from '../../views/CourseLearn.vue'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

import api from '../../api/client'

const defaultLessons = [{
  id: 'lesson-1', title: 'Aula de Teste', order: 1, content_type: 'YOUTUBE',
  video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', is_free_preview: false,
  is_required: true, completed: false,
}]

const buildRouter = () => createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div></div>' } },
    { path: '/dashboard', component: { template: '<div></div>' } },
    { path: '/cursos', component: { template: '<div></div>' } },
    { path: '/certificates', component: { template: '<div></div>' } },
    { path: '/validar-certificado', component: { template: '<div></div>' } },
    { path: '/seja-parceiro', component: { template: '<div></div>' } },
    { path: '/login', component: { template: '<div></div>' } },
    { path: '/register', component: { template: '<div></div>' } },
    { path: '/courses/:id/learn', name: 'CourseLearn', component: CourseLearn },
    { path: '/:pathMatch(.*)*', component: { template: '<div></div>' } },
  ],
})

function mockCourse(lessons = defaultLessons, required = 1) {
  api.get.mockImplementation((url) => {
    if (url.includes('/my-progress')) return Promise.resolve({ data: { percentage: 0, completed_required: 0, required_lessons: required } })
    if (url.includes('/lessons/courses/')) return Promise.resolve({ data: lessons })
    if (url.includes('/assessments/courses/')) return Promise.resolve({ data: { required: false, lessons_complete: false, minimum_score: 60, passed: false } })
    if (url.includes('/courses/')) return Promise.resolve({ data: { id: 'course-1', name: 'Curso Teste' } })
    if (url.includes('/watch-url')) return Promise.resolve({ data: { watch_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' } })
    return Promise.resolve({ data: {} })
  })
}

async function mountLearn() {
  const router = buildRouter()
  await router.push('/courses/course-1/learn')
  await router.isReady()
  const wrapper = mount(CourseLearn, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('CourseLearn View', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    vi.clearAllMocks()
    mockCourse()
  })

  it('renderiza o nome do curso e as aulas', async () => {
    const wrapper = await mountLearn()
    expect(wrapper.text()).toContain('Curso Teste')
    expect(wrapper.text()).toContain('Aula de Teste')
  })

  it('permite assistir aula para aluno matriculado', async () => {
    const wrapper = await mountLearn()
    const lessonButton = wrapper.findAll('button').find((b) => b.text().includes('Aula de Teste'))
    await lessonButton.trigger('click')
    await flushPromises()
    expect(wrapper.html()).toContain('youtube.com')
  })

  it('preserva ordem 1-based no badge e data-lesson-order (regressão BUG-2)', async () => {
    const lessons = [
      { id: 'l1', title: 'Introdução', order: 1, content_type: 'YOUTUBE', is_required: true, completed: false },
      { id: 'l2', title: 'Conceitos', order: 2, content_type: 'YOUTUBE', is_required: true, completed: false },
      { id: 'l3', title: 'Procedimentos', order: 3, content_type: 'YOUTUBE', is_required: true, completed: false },
      { id: 'l4', title: 'Aplicação', order: 4, content_type: 'YOUTUBE', is_required: true, completed: false },
      { id: 'l5', title: 'Encerramento', order: 5, content_type: 'YOUTUBE', is_required: false, completed: false },
    ]
    mockCourse(lessons, 4)
    const wrapper = await mountLearn()

    const titles = wrapper.findAll('[data-testid="lesson-title"]')
    expect(titles).toHaveLength(5)
    expect(titles.map((item) => item.text())).toEqual(['Introdução', 'Conceitos', 'Procedimentos', 'Aplicação', 'Encerramento'])

    const rows = wrapper.findAll('[data-testid="lesson-row"]')
    expect(rows).toHaveLength(5)
    expect(rows.map((row) => row.attributes('data-lesson-order'))).toEqual(['1', '2', '3', '4', '5'])
    expect(rows[0].find('span').text()).toBe('1')
    expect(rows[4].find('span').text()).toBe('5')
    expect(rows[0].find('span').text()).not.toBe('2')
    expect(rows[4].find('span').text()).not.toBe('6')
  })

  it('não mascara erro da API de aulas como curso vazio', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/lessons/courses/')) {
        return Promise.reject({ response: { status: 500, data: { detail: 'Falha temporária no serviço de aulas' } } })
      }
      if (url.includes('/my-progress')) return Promise.resolve({ data: { percentage: 0, completed_required: 0, required_lessons: 4 } })
      if (url.includes('/assessments/courses/')) return Promise.resolve({ data: { required: false, lessons_complete: false, minimum_score: 60, passed: false } })
      if (url.includes('/courses/')) return Promise.resolve({ data: { id: 'course-1', name: 'Curso Teste' } })
      return Promise.resolve({ data: {} })
    })

    const wrapper = await mountLearn()

    expect(wrapper.find('[data-testid="lessons-load-error"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="lessons-load-error"]').text()).toContain('Falha temporária no serviço de aulas')
    expect(wrapper.find('[data-testid="lessons-empty"]').exists()).toBe(false)
  })

  it('mostra estado vazio somente quando a API retorna lista vazia com sucesso', async () => {
    mockCourse([], 0)
    const wrapper = await mountLearn()

    expect(wrapper.find('[data-testid="lessons-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="lessons-load-error"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Nenhuma aula foi cadastrada para este curso.')
  })

  it('exibe a avaliação ao abrir um curso já 100% concluído', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/my-progress')) return Promise.resolve({ data: { percentage: 100, completed_required: 1, required_lessons: 1 } })
      if (url.includes('/lessons/courses/')) return Promise.resolve({ data: [{ ...defaultLessons[0], completed: true }] })
      if (url.includes('/assessments/courses/')) return Promise.resolve({ data: { required: true, lessons_complete: true, minimum_score: 60, passed: false } })
      if (url.includes('/courses/')) return Promise.resolve({ data: { id: 'course-1', name: 'Curso Teste' } })
      return Promise.resolve({ data: {} })
    })

    const wrapper = await mountLearn()

    expect(wrapper.find('[data-testid="final-assessment-card"]').attributes('data-assessment-status')).toBe('available')
    expect(wrapper.find('[data-testid="assessment-start-button"]').exists()).toBe(true)
  })

  it('mostra erro explícito e retry quando a consulta da avaliação retorna 429', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/my-progress')) return Promise.resolve({ data: { percentage: 100, completed_required: 1, required_lessons: 1 } })
      if (url.includes('/lessons/courses/')) return Promise.resolve({ data: [{ ...defaultLessons[0], completed: true }] })
      if (url.includes('/assessments/courses/')) {
        return Promise.reject({ response: { status: 429, data: { detail: 'Rate limit exceeded' } } })
      }
      if (url.includes('/courses/')) return Promise.resolve({ data: { id: 'course-1', name: 'Curso Teste' } })
      return Promise.resolve({ data: {} })
    })

    const wrapper = await mountLearn()

    expect(wrapper.find('[data-testid="assessment-status-error"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="assessment-status-error"]').text()).toContain('Rate limit exceeded')
    expect(wrapper.find('[data-testid="assessment-retry-button"]').exists()).toBe(true)
  })

  it('retry bem-sucedido libera a avaliação sem recarregar a página', async () => {
    let assessmentCalls = 0
    api.get.mockImplementation((url) => {
      if (url.includes('/my-progress')) return Promise.resolve({ data: { percentage: 100, completed_required: 1, required_lessons: 1 } })
      if (url.includes('/lessons/courses/')) return Promise.resolve({ data: [{ ...defaultLessons[0], completed: true }] })
      if (url.includes('/assessments/courses/')) {
        assessmentCalls += 1
        if (assessmentCalls === 1) {
          return Promise.reject({ response: { status: 429, data: { detail: 'Rate limit exceeded' } } })
        }
        return Promise.resolve({ data: { required: true, lessons_complete: true, minimum_score: 60, passed: false } })
      }
      if (url.includes('/courses/')) return Promise.resolve({ data: { id: 'course-1', name: 'Curso Teste' } })
      return Promise.resolve({ data: {} })
    })

    const wrapper = await mountLearn()
    expect(wrapper.find('[data-testid="assessment-status-error"]').exists()).toBe(true)

    await wrapper.find('[data-testid="assessment-retry-button"]').trigger('click')
    await flushPromises()

    expect(assessmentCalls).toBe(2)
    expect(wrapper.find('[data-testid="assessment-status-error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="assessment-start-button"]').exists()).toBe(true)
  })

  it('reconsulta o status uma única vez após concluir uma aula manualmente', async () => {
    let assessmentCalls = 0
    api.get.mockImplementation((url) => {
      if (url.includes('/my-progress')) return Promise.resolve({ data: { percentage: 100, completed_required: 1, required_lessons: 1 } })
      if (url.includes('/lessons/courses/')) return Promise.resolve({ data: defaultLessons })
      if (url.includes('/assessments/courses/')) {
        assessmentCalls += 1
        return Promise.resolve({ data: { required: true, lessons_complete: assessmentCalls > 1, minimum_score: 60, passed: false } })
      }
      if (url.includes('/courses/')) return Promise.resolve({ data: { id: 'course-1', name: 'Curso Teste' } })
      if (url.includes('/watch-url')) return Promise.resolve({ data: { watch_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' } })
      return Promise.resolve({ data: {} })
    })
    api.post.mockResolvedValue({ data: {} })

    const wrapper = await mountLearn()
    const lessonButton = wrapper.findAll('button').find((button) => button.text().includes('Aula de Teste'))
    await lessonButton.trigger('click')
    await flushPromises()

    const completeButton = wrapper.findAll('button').find((button) => button.text().includes('Marcar como concluída'))
    await completeButton.trigger('click')
    await flushPromises()

    expect(assessmentCalls).toBe(2)
    expect(wrapper.find('[data-testid="assessment-start-button"]').exists()).toBe(true)
  })
})
