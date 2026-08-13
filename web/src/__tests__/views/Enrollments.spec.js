import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../../stores/auth'
import Enrollments from '../../views/Enrollments.vue'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

describe('Enrollments View', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
  })

  it('renderiza a página de matrículas', async () => {
    const wrapper = mount(Enrollments)
    await flushPromises()
    expect(wrapper.text()).toContain('Matrículas')
  })

  it('exibe botão de nova matrícula para admin', async () => {
    const wrapper = mount(Enrollments)
    await flushPromises()
    expect(wrapper.text()).toContain('+ Nova Matrícula')
  })

  it('mostra mensagem quando não há matrículas', async () => {
    const wrapper = mount(Enrollments)
    await flushPromises()
    expect(wrapper.text()).toContain('Nenhuma matrícula cadastrada')
  })
})
