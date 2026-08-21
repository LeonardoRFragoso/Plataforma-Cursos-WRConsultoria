import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DemoPayment from '../../views/DemoPayment.vue'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '../../api/client'

const setupRouter = () => {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/demo/payment/:paymentId', component: DemoPayment },
      { path: '/courses/:id/learn', component: { template: '<div class="learn-page"></div>' } },
    ],
  })
}

const paymentData = {
  payment_id: 'pay-123',
  course_id: 'course-456',
  course_name: 'NR-10 Segurança',
  amount: 299.90,
  status: 'PENDENTE',
  student_name: 'João Silva',
  enrollment_status: 'PENDENTE',
}

describe('DemoPayment View', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  async function mountComponent(paymentId = 'pay-123') {
    const router = setupRouter()
    await router.push(`/demo/payment/${paymentId}`)
    await router.isReady()

    api.get.mockResolvedValue({ data: paymentData })

    const wrapper = mount(DemoPayment, {
      global: { plugins: [router, createPinia()] },
    })
    await flushPromises()
    return { wrapper, router }
  }

  it('loads payment details on mount', async () => {
    const { wrapper } = await mountComponent()
    expect(api.get).toHaveBeenCalledWith('/api/v1/payments/demo/pay-123')
    expect(wrapper.text()).toContain('NR-10 Segurança')
    expect(wrapper.text()).toContain('João Silva')
  })

  it('shows amount and status', async () => {
    const { wrapper } = await mountComponent()
    expect(wrapper.text()).toContain('299.9')
    expect(wrapper.text()).toContain('PENDENTE')
  })

  it('approve action calls API and updates status', async () => {
    api.post.mockResolvedValue({
      data: {
        status: 'approved',
        payment_status: 'APROVADO',
        enrollment_status: 'CONFIRMADA',
        enrollment_confirmed: true,
        amount_match: true,
      },
    })
    // After approve, the GET reload returns updated status
    api.get.mockResolvedValueOnce({ data: paymentData })
      .mockResolvedValueOnce({
        data: { ...paymentData, status: 'APROVADO', enrollment_status: 'CONFIRMADA' },
      })
    const { wrapper } = await mountComponent()

    const approveBtn = wrapper.find('[data-testid="approve-btn"]')
    await approveBtn.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/api/v1/payments/demo/pay-123/approve')
    expect(wrapper.text()).toContain('APROVADO')
  })

  it('pending action calls API', async () => {
    api.post.mockResolvedValue({
      data: { status: 'pending', payment_status: 'PROCESSANDO' },
    })
    const { wrapper } = await mountComponent()

    const pendingBtn = wrapper.find('[data-testid="pending-btn"]')
    await pendingBtn.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/api/v1/payments/demo/pay-123/pending')
  })

  it('reject action calls API', async () => {
    api.post.mockResolvedValue({
      data: { status: 'rejected', payment_status: 'RECUSADO' },
    })
    const { wrapper } = await mountComponent()

    const rejectBtn = wrapper.find('[data-testid="reject-btn"]')
    await rejectBtn.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/api/v1/payments/demo/pay-123/reject')
  })

  it('shows Acessar Curso link with valid course_id after approval', async () => {
    api.post.mockResolvedValue({
      data: {
        status: 'approved',
        payment_status: 'APROVADO',
        enrollment_status: 'CONFIRMADA',
        enrollment_confirmed: true,
        amount_match: true,
      },
    })
    api.get.mockResolvedValueOnce({ data: paymentData })
      .mockResolvedValueOnce({
        data: { ...paymentData, status: 'APROVADO', enrollment_status: 'CONFIRMADA' },
      })
    const { wrapper } = await mountComponent()

    const approveBtn = wrapper.find('[data-testid="approve-btn"]')
    await approveBtn.trigger('click')
    await flushPromises()

    const link = wrapper.find('[data-testid="access-course-link"]')
    expect(link.exists()).toBe(true)
    // router-link renders as <a> with href in test environment, or check the to prop
    const href = link.attributes('href')
    const to = link.attributes('to')
    expect(href || to).toContain('course-456')
  })

  it('does not show Acessar Curso link when enrollment is not confirmed', async () => {
    const { wrapper } = await mountComponent()
    const link = wrapper.find('[data-testid="access-course-link"]')
    expect(link.exists()).toBe(false)
  })

  it('handles API error on load', async () => {
    api.get.mockRejectedValue({
      response: { data: { detail: 'Payment not found' } },
    })

    const router = setupRouter()
    await router.push('/demo/payment/bad-id')
    await router.isReady()

    const wrapper = mount(DemoPayment, {
      global: { plugins: [router, createPinia()] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Payment not found')
  })

  it('handles API error on approve action', async () => {
    api.post.mockRejectedValue({
      response: { data: { detail: 'Not authorized' } },
    })
    const { wrapper } = await mountComponent()

    const approveBtn = wrapper.find('[data-testid="approve-btn"]')
    await approveBtn.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Not authorized')
  })
})
