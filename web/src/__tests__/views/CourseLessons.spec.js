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
        {
          path: '/courses/:id/progress',
          name: 'CourseProgress',
          component: { template: '<div></div>' },
        },
      ],
    })

    api.get.mockImplementation((url) => {
      if (url.includes('/lessons/courses/') && url.includes('/lessons')) {
        return Promise.resolve({
          data: [
            {
              id: 'lesson-1',
              title: 'Aula 1',
              order: 0,
              content_type: 'UPLOAD',
              is_free_preview: true,
              is_required: false,
              storage_key: null,
              duration_seconds: 300,
            },
            {
              id: 'lesson-2',
              title: 'Aula 2',
              order: 1,
              content_type: 'UPLOAD',
              is_free_preview: false,
              is_required: true,
              storage_key: 'tenants/x/courses/y/lessons/z/video/v.mp4',
              duration_seconds: 600,
            },
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

    api.post.mockResolvedValue({ data: {} })
    api.put.mockResolvedValue({ data: [] })
    api.delete.mockResolvedValue({ data: {} })
  })

  it('renderiza lista de aulas para admin', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Aula 1')
    expect(wrapper.text()).toContain('Aula 2')
  })

  it('chama API para carregar curso e aulas', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(api.get).toHaveBeenCalled()
  })

  it('exibe badges de grátis e obrigatória', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Grátis')
    expect(wrapper.text()).toContain('Obrigatória')
    expect(wrapper.text()).toContain('Opcional')
  })

  it('exibe botão de enviar vídeo quando storage_key vazio', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Enviar Vídeo')
    expect(wrapper.text()).toContain('Trocar Vídeo')
  })

  it('exibe botão de remover vídeo quando storage_key preenchido', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Remover Vídeo')
  })

  it('exibe botão de materiais e progresso', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Materiais')
    expect(wrapper.text()).toContain('Progresso dos Alunos')
  })

  it('exibe controles de reordenação', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const buttons = wrapper.findAll('button')
    const upDownButtons = buttons.filter(b => b.text() === '▲' || b.text() === '▼')
    expect(upDownButtons.length).toBeGreaterThan(0)
  })

  it('abre formulário com campo is_required ao clicar em Nova Aula', async () => {
    await router.push('/courses/course-1/lessons')
    await router.isReady()

    const wrapper = mount(CourseLessons, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const novaAulaBtn = wrapper.findAll('button').find(b => b.text().includes('Nova Aula'))
    await novaAulaBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Aula obrigatória')
  })
})
