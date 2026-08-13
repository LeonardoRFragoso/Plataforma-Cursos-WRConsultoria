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
          },
        })
      }
      if (url.includes('/lessons/courses/')) {
        return Promise.resolve({
          data: [
            {
              id: 'lesson-1',
              title: 'Aula de Teste',
              order: 0,
              content_type: 'YOUTUBE',
              video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
              is_free_preview: false,
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
})
