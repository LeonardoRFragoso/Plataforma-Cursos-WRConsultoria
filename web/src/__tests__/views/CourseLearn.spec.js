import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { createRouter, createMemoryHistory } from 'vue-router'
import CourseLearn from '../../views/CourseLearn.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../../api/client'

describe('CourseLearn View', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'

    vi.clearAllMocks()

    api.get.mockImplementation((url) => {
      if (url.includes('/my-progress')) {
        return Promise.resolve({
          data: {
            is_enrolled: true,
            completed: 0,
            total: 1,
            lessons: [],
            percentage: 0,
            completed_required: 0,
            required_lessons: 0,
          },
        })
      }
      if (url.includes('/lessons/courses/')) {
        return Promise.resolve({
          data: [
            {
              id: 'lesson-1',
              title: 'Aula de Teste',
              order: 1,
              content_type: 'YOUTUBE',
              video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
              is_free_preview: false,
              is_required: true,
              completed: false,
            },
          ],
        })
      }
      if (url.includes('/courses/')) {
        return Promise.resolve({
          data: { id: 'course-1', name: 'Curso Teste' },
        })
      }
      return Promise.resolve({ data: {} })
    })

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/courses/:id/learn',
          name: 'CourseLearn',
          component: CourseLearn,
        },
      ],
    })
  })

  it('renderiza o nome do curso e as aulas', async () => {
    await router.push('/courses/course-1/learn')
    await router.isReady()

    const wrapper = mount(CourseLearn, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Curso Teste')
    expect(wrapper.text()).toContain('Aula de Teste')
  })

  it('permite assistir aula para aluno matriculado', async () => {
    await router.push('/courses/course-1/learn')
    await router.isReady()

    const wrapper = mount(CourseLearn, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    const lessonButton = wrapper
      .findAll('button')
      .find((b) => b.text().includes('Aula de Teste'))
    await lessonButton.trigger('click')
    await flushPromises()

    expect(wrapper.html()).toContain('youtube.com')
  })

  it('displays 1-based lesson order without +1 offset (regression for BUG-2)', async () => {
    // Override the mock to return 5 lessons with orders 1..5
    api.get.mockImplementation((url) => {
      if (url.includes('/my-progress')) {
        return Promise.resolve({
          data: {
            percentage: 0,
            completed_required: 0,
            required_lessons: 4,
          },
        })
      }
      if (url.includes('/lessons/courses/')) {
        return Promise.resolve({
          data: [
            { id: 'l1', title: 'Introdução', order: 1, content_type: 'YOUTUBE', is_required: true, completed: false },
            { id: 'l2', title: 'Conceitos', order: 2, content_type: 'YOUTUBE', is_required: true, completed: false },
            { id: 'l3', title: 'Procedimentos', order: 3, content_type: 'YOUTUBE', is_required: true, completed: false },
            { id: 'l4', title: 'Aplicação', order: 4, content_type: 'YOUTUBE', is_required: true, completed: false },
            { id: 'l5', title: 'Encerramento', order: 5, content_type: 'YOUTUBE', is_required: false, completed: false },
          ],
        })
      }
      if (url.includes('/courses/')) {
        return Promise.resolve({ data: { id: 'course-1', name: 'Curso Teste' } })
      }
      return Promise.resolve({ data: {} })
    })

    await router.push('/courses/course-1/learn')
    await router.isReady()

    const wrapper = mount(CourseLearn, {
      global: { plugins: [router] },
    })
    await flushPromises()

    // Lesson titles must display the real 1-based order, NOT order+1
    const titles = wrapper.findAll('[data-testid="lesson-title"]')
    expect(titles).toHaveLength(5)
    expect(titles[0].text()).toContain('1. Introdução')
    expect(titles[1].text()).toContain('2. Conceitos')
    expect(titles[2].text()).toContain('3. Procedimentos')
    expect(titles[3].text()).toContain('4. Aplicação')
    expect(titles[4].text()).toContain('5. Encerramento')

    // Must NOT display 2..6 (the old +1 bug)
    expect(titles[0].text()).not.toContain('2. Introdução')
    expect(titles[4].text()).not.toContain('6. Encerramento')

    // data-lesson-order must still be the raw order value
    const rows = wrapper.findAll('[data-testid="lesson-row"]')
    expect(rows).toHaveLength(5)
    expect(rows[0].attributes('data-lesson-order')).toBe('1')
    expect(rows[4].attributes('data-lesson-order')).toBe('5')
  })
})
