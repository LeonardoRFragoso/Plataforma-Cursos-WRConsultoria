import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Partner from '../../views/Partner.vue'

vi.mock('../../api/partner', () => ({
  submitPartnerLead: vi.fn(),
}))

import { submitPartnerLead } from '../../api/partner'

function setupRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/seja-parceiro', component: { template: '<div>partner</div>' } },
    ],
  })
}

async function mountView() {
  const router = setupRouter()
  await router.push('/seja-parceiro')
  await router.isReady()
  return mount(Partner, { global: { plugins: [router] } })
}

describe('Partner', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    submitPartnerLead.mockReset()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders form with required fields', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('[data-testid="partner-company-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="partner-contact-name-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="partner-email-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="partner-submit-btn"]').exists()).toBe(true)
  })

  it('shows loading state on submit', async () => {
    submitPartnerLead.mockReturnValue(new Promise(() => {}))
    const wrapper = await mountView()
    await wrapper.find('[data-testid="partner-company-input"]').setValue('TestCo')
    await wrapper.find('[data-testid="partner-contact-name-input"]').setValue('John')
    await wrapper.find('[data-testid="partner-email-input"]').setValue('john@test.co')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.find('[data-testid="partner-submit-btn"]').text()).toContain('Enviando')
    expect(wrapper.find('[data-testid="partner-submit-btn"]').attributes('disabled')).toBeDefined()
  })

  it('shows success state after valid submission', async () => {
    submitPartnerLead.mockResolvedValue({})
    const wrapper = await mountView()
    await wrapper.find('[data-testid="partner-company-input"]').setValue('TestCo')
    await wrapper.find('[data-testid="partner-contact-name-input"]').setValue('John')
    await wrapper.find('[data-testid="partner-email-input"]').setValue('john@test.co')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="partner-success"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Proposta recebida')
  })

  it('prevents duplicate submission (loading guard)', async () => {
    submitPartnerLead.mockReturnValue(new Promise(() => {})) // never resolves
    const wrapper = await mountView()
    await wrapper.find('[data-testid="partner-company-input"]').setValue('TestCo')
    await wrapper.find('[data-testid="partner-contact-name-input"]').setValue('John')
    await wrapper.find('[data-testid="partner-email-input"]').setValue('john@test.co')
    await wrapper.find('form').trigger('submit.prevent')
    // Try to submit again
    await wrapper.find('form').trigger('submit.prevent')
    // Should only have been called once
    expect(submitPartnerLead).toHaveBeenCalledTimes(1)
  })

  it('shows error on server failure', async () => {
    submitPartnerLead.mockRejectedValue({
      response: { data: { detail: 'Server error' } },
    })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="partner-company-input"]').setValue('TestCo')
    await wrapper.find('[data-testid="partner-contact-name-input"]').setValue('John')
    await wrapper.find('[data-testid="partner-email-input"]').setValue('john@test.co')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="partner-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Server error')
  })

  it('shows generic error on network failure', async () => {
    submitPartnerLead.mockRejectedValue(new Error('Network'))
    const wrapper = await mountView()
    await wrapper.find('[data-testid="partner-company-input"]').setValue('TestCo')
    await wrapper.find('[data-testid="partner-contact-name-input"]').setValue('John')
    await wrapper.find('[data-testid="partner-email-input"]').setValue('john@test.co')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="partner-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Erro ao enviar proposta')
  })

  it('allows new submission after success via reset link', async () => {
    submitPartnerLead.mockResolvedValue({})
    const wrapper = await mountView()
    await wrapper.find('[data-testid="partner-company-input"]').setValue('TestCo')
    await wrapper.find('[data-testid="partner-contact-name-input"]').setValue('John')
    await wrapper.find('[data-testid="partner-email-input"]').setValue('john@test.co')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    // Click "Enviar nova proposta"
    await wrapper.find('[data-testid="partner-new-submission"]').trigger('click')
    // Form should be visible again
    expect(wrapper.find('[data-testid="partner-company-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="partner-company-input"]').element.value).toBe('')
  })
})
