import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import NrTutorAssistant from '../../components/NrTutorAssistant.vue'
import api from '../../api/client'

describe('NrTutorAssistant', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('renders toggle button and opens the panel', async () => {
    const wrapper = mount(NrTutorAssistant)

    expect(wrapper.find('[data-testid="nr-tutor-toggle"]').exists()).toBe(true)

    await wrapper.find('[data-testid="nr-tutor-toggle"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="tutor-input"]').exists()).toBe(true)
  })

  it('sends a question and displays the answer with sources', async () => {
    api.post.mockResolvedValueOnce({
      data: {
        answer: 'O EPI deve ser fornecido pelo empregador e adequado ao risco.',
        sources: [
          { label: 'NR-06 — Equipamento de Proteção Individual (EPI)', nr_code: 'NR-06', variant: '', heading: '' },
        ],
        suggestions: ['Quais EPIs são obrigatórios?'],
        confidence: 'HIGH',
        scope: ['NR-06'],
        knowledge_level: 'DEEP_KNOWLEDGE',
      },
    })

    const wrapper = mount(NrTutorAssistant)
    await wrapper.find('[data-testid="nr-tutor-toggle"]').trigger('click')
    await flushPromises()

    const input = wrapper.find('[data-testid="tutor-input"]')
    await input.setValue('Qual EPI devo utilizar?')
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/api/v1/tutor/ask', {
      question: 'Qual EPI devo utilizar?',
      conversation_context: expect.any(Array),
    })
    expect(wrapper.text()).toContain('fornecido pelo empregador')
    expect(wrapper.find('[data-testid="tutor-source-chip"]').text()).toContain('NR-06')
  })

  it('shows loading state while waiting for the answer', async () => {
    let resolvePost
    api.post.mockReturnValueOnce(
      new Promise((resolve) => { resolvePost = resolve })
    )

    const wrapper = mount(NrTutorAssistant)
    await wrapper.find('[data-testid="nr-tutor-toggle"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="tutor-input"]').setValue('O que é SEP?')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    // During the request, the send button is disabled and typing dots are present
    expect(wrapper.find('[aria-label="Tutor digitando"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tutor-send-btn"]').attributes('disabled')).toBeDefined()

    resolvePost({
      data: {
        answer: 'SEP é o Sistema Elétrico de Potência.',
        sources: [],
        suggestions: [],
        confidence: 'MEDIUM',
        scope: ['NR-10'],
        knowledge_level: 'DEEP_KNOWLEDGE',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Sistema Elétrico de Potência')
  })

  it('displays an error message and allows retry', async () => {
    api.post.mockRejectedValueOnce(new Error('Network error'))

    const wrapper = mount(NrTutorAssistant)
    await wrapper.find('[data-testid="nr-tutor-toggle"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="tutor-input"]').setValue('como usar cinto?')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Resposta do modo offline')
    expect(wrapper.find('[data-testid="tutor-retry-btn"]').exists()).toBe(true)
  })

  it('resets the conversation', async () => {
    api.post.mockResolvedValueOnce({
      data: {
        answer: 'Resposta temporária.',
        sources: [],
        suggestions: ['Sugestão 1'],
        confidence: 'LOW',
        scope: [],
        knowledge_level: 'NO_CONFIDENT_SOURCE',
      },
    })

    const wrapper = mount(NrTutorAssistant)
    await wrapper.find('[data-testid="nr-tutor-toggle"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="tutor-input"]').setValue('pergunta teste')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Resposta temporária')

    // Find the reset button (title attribute)
    const resetBtn = wrapper.find('button[title="Limpar conversa"]')
    await resetBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('assistente virtual de estudo')
  })

  it('sends a suggestion when clicked', async () => {
    api.post.mockResolvedValueOnce({
      data: {
        answer: 'Trabalho em altura requer ancoragem segura.',
        sources: [],
        suggestions: [],
        confidence: 'HIGH',
        scope: ['NR-35'],
        knowledge_level: 'DEEP_KNOWLEDGE',
      },
    })

    const wrapper = mount(NrTutorAssistant)
    await wrapper.find('[data-testid="nr-tutor-toggle"]').trigger('click')
    await flushPromises()

    const suggestions = wrapper.findAll('button.rounded-full')
    const first = suggestions.find((b) => b.text().includes('NR-6'))
    expect(first).toBeDefined()
    await first.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalled()
    const call = api.post.mock.calls[0]
    expect(call[0]).toBe('/api/v1/tutor/ask')
    expect(call[1].question).toContain('NR-6')
  })

  it('keeps conversation context for follow-up questions', async () => {
    api.post
      .mockResolvedValueOnce({
        data: {
          answer: 'SEP é o Sistema Elétrico de Potência.',
          sources: [],
          suggestions: [],
          confidence: 'HIGH',
          scope: ['NR-10'],
          knowledge_level: 'DEEP_KNOWLEDGE',
        },
      })
      .mockResolvedValueOnce({
        data: {
          answer: 'Apenas trabalhadores autorizados e qualificados.',
          sources: [],
          suggestions: [],
          confidence: 'HIGH',
          scope: ['NR-10'],
          knowledge_level: 'DEEP_KNOWLEDGE',
        },
      })

    const wrapper = mount(NrTutorAssistant)
    await wrapper.find('[data-testid="nr-tutor-toggle"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="tutor-input"]').setValue('O que é SEP?')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    await wrapper.find('[data-testid="tutor-input"]').setValue('E quem pode trabalhar?')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(2)
    const secondCall = api.post.mock.calls[1]
    const secondCallContext = secondCall[1].conversation_context
    expect(secondCallContext.length).toBeGreaterThan(0)
    expect(secondCallContext.some((m) => m.text.includes('SEP'))).toBe(true)
  })
})
