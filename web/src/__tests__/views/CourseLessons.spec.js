import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import { createRouter, createMemoryHistory } from 'vue-router'
import CourseLessons from '../../views/CourseLessons.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../../api/client'

describe('CourseLessons View', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'

    vi.clearAllMocks()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/courses/:id/lessons',
          name: 'CourseLessons',
          component: CourseLessons,
        },
      ],
    })

    api.get.mockImplementation((url) => {
      if (url.includes('/lessons/courses/')) {
        return Promise.resolve({
          data: [
            { id: 'lesson-1', title: 'Aula 1', order: 0 },
            { id: 'lesson-2', title: 'Aula 2', order: 1 },
          ],
        })
      }
      if (url.includes('/courses/')) {
        return Promise.resolve({
          data: { id: 'course-1', name: 'Curso Administrado' },
        })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renderiza lista de aulas para admin', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Aula 1')
    expect(wrapper.text()).toContain('Aula 2')
  })

  it('chama API para carregar curso e aulas', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: {
        plugins: [router],
      },
    })
    await flushPromises()

    expect(api.get).toHaveBeenCalled()
  })
})
