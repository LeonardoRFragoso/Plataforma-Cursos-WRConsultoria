import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import PaymentReturn from '../../views/PaymentReturn.vue'

// Mock API client
vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

const api = (await import('../../api/client')).default

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/payment/return/:paymentId', name: 'PaymentReturn', component: PaymentReturn },
      { path: '/dashboard', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/cursos', name: 'CourseCatalog', component: { template: '<div>Catalog</div>' } },
      { path: '/courses/:id', name: 'CourseDetail', component: { template: '<div>Course</div>' } },
      { path: '/courses/:id/learn', name: 'CourseLearn', component: { template: '<div>Learn</div>' } },
    ],
  })
}

describe('PaymentReturn', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    api.get.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows processing state with polling message when payment is PROCESSANDO', async () => {
    api.get.mockResolvedValue({ data: { status: 'PROCESSANDO', course_id: 'abc-123' } })
    const router = makeRouter()
    await router.push('/payment/return/pay-1')
    await router.isReady()

    const wrapper = mount(PaymentReturn, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('[data-testid="refresh-btn"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Estamos confirmando seu pagamento')
  })

  it('shows approved state with access course link when payment is APROVADO', async () => {
    api.get.mockResolvedValue({
      data: { status: 'APROVADO', course_id: 'course-1', enrollment_status: 'CONFIRMADA' },
    })
    const router = makeRouter()
    await router.push('/payment/return/pay-1')
    await router.isReady()

    const wrapper = mount(PaymentReturn, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('[data-testid="access-course-link"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="access-course-link"]').attributes('href')).toBe('/courses/course-1/learn')
    expect(wrapper.text()).toContain('Pagamento confirmado')
  })

  it('refused payment returns to the course for a new payment attempt', async () => {
    api.get.mockResolvedValue({
      data: {
        status: 'RECUSADO',
        course_id: 'course-1',
        checkout_url: 'https://checkout.test/old-attempt',
      },
    })
    const router = makeRouter()
    await router.push('/payment/return/pay-1')
    await router.isReady()

    const wrapper = mount(PaymentReturn, { global: { plugins: [router] } })
    await flushPromises()

    const retryLink = wrapper.find('[data-testid="retry-payment-link"]')
    expect(retryLink.exists()).toBe(true)
    expect(retryLink.attributes('href')).toBe('/courses/course-1')
    expect(wrapper.text()).toContain('Esta tentativa foi encerrada')
    expect(wrapper.html()).not.toContain('https://checkout.test/old-attempt')
  })

  it('refused payment without course context falls back to catalog', async () => {
    api.get.mockResolvedValue({ data: { status: 'RECUSADO' } })
    const router = makeRouter()
    await router.push('/payment/return/pay-1')
    await router.isReady()

    const wrapper = mount(PaymentReturn, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('[data-testid="retry-payment-link"]').attributes('href')).toBe('/cursos')
  })

  it('shows error state when API fails', async () => {
    api.get.mockRejectedValue({ response: { data: { detail: 'Not found' } } })
    const router = makeRouter()
    await router.push('/payment/return/pay-1')
    await router.isReady()

    const wrapper = mount(PaymentReturn, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('[data-testid="retry-btn"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Not found')
  })

  it('polls internal API and stops when payment becomes APROVADO', async () => {
    // First call returns PROCESSANDO, second returns APROVADO
    api.get
      .mockResolvedValueOnce({ data: { status: 'PROCESSANDO', course_id: 'c1' } })
      .mockResolvedValueOnce({ data: { status: 'APROVADO', course_id: 'c1' } })

    const router = makeRouter()
    await router.push('/payment/return/pay-1')
    await router.isReady()

    const wrapper = mount(PaymentReturn, { global: { plugins: [router] } })
    await flushPromises()

    // Should be in processing state
    expect(wrapper.find('[data-testid="refresh-btn"]').exists()).toBe(true)

    // Advance timer to trigger poll
    await vi.advanceTimersByTimeAsync(6000)
    await flushPromises()

    // Should now show approved state
    expect(wrapper.find('[data-testid="access-course-link"]').exists()).toBe(true)

    // Only 2 API calls: initial load + 1 poll
    expect(api.get).toHaveBeenCalledTimes(2)
    // All calls go to internal API, never to Asaas
    expect(api.get).toHaveBeenCalledWith('/api/v1/payments/pay-1')
  })
})