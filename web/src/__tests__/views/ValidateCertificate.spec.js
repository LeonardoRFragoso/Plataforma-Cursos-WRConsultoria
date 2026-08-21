import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ValidateCertificate from '../../views/ValidateCertificate.vue'

vi.mock('../../api/certificates', () => ({
  validateCertificate: vi.fn(),
}))

import { validateCertificate } from '../../api/certificates'

function setupRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/validar-certificado', component: { template: '<div>validate</div>' } },
    ],
  })
}

async function mountView() {
  const router = setupRouter()
  await router.push('/validar-certificado')
  await router.isReady()
  return mount(ValidateCertificate, { global: { plugins: [router] } })
}

describe('ValidateCertificate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    validateCertificate.mockReset()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders initial state with code input and submit button', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('[data-testid="validate-code-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="validate-submit-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="validate-invalid"]').exists()).toBe(false)
  })

  it('shows loading state during validation', async () => {
    validateCertificate.mockReturnValue(new Promise(() => {}))
    const wrapper = await mountView()
    await wrapper.find('[data-testid="validate-code-input"]').setValue('ABC-123')
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.find('[data-testid="validate-submit-btn"]').text()).toContain('Verificando')
    expect(wrapper.find('[data-testid="validate-submit-btn"]').attributes('disabled')).toBeDefined()
  })

  it('shows valid certificate state on success', async () => {
    validateCertificate.mockResolvedValue({
      data: {
        valid: true,
        certificate_number: 'CERT-001',
        student_name: 'João Silva',
        course_name: 'NR-10',
        issued_at: '2026-01-15T10:00:00Z',
      },
    })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="validate-code-input"]').setValue('VALID-CODE')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Certificado válido')
    expect(wrapper.text()).toContain('João Silva')
    expect(wrapper.text()).toContain('NR-10')
  })

  it('shows invalid state on 404 (not found)', async () => {
    validateCertificate.mockRejectedValue({ response: { status: 404 } })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="validate-code-input"]').setValue('INVALID-CODE')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-invalid"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('não foi localizado')
    // Should NOT show server error
    expect(wrapper.find('[data-testid="validate-server-error"]').exists()).toBe(false)
  })

  it('shows invalid state on 400 (bad request)', async () => {
    validateCertificate.mockRejectedValue({ response: { status: 400 } })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="validate-code-input"]').setValue('BAD-CODE')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-invalid"]').exists()).toBe(true)
  })

  it('shows server error on 5xx (network/server failure)', async () => {
    validateCertificate.mockRejectedValue({ response: { status: 500 } })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="validate-code-input"]').setValue('SOME-CODE')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-server-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Não foi possível verificar')
    // Should NOT show invalid state (that's for not-found, not server errors)
    expect(wrapper.find('[data-testid="validate-invalid"]').exists()).toBe(false)
  })

  it('shows server error on network failure (no response)', async () => {
    validateCertificate.mockRejectedValue(new Error('Network'))
    const wrapper = await mountView()
    await wrapper.find('[data-testid="validate-code-input"]').setValue('SOME-CODE')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-server-error"]').exists()).toBe(true)
  })

  it('clears previous results on new submission', async () => {
    // First: valid
    validateCertificate.mockResolvedValue({ data: { valid: true, certificate_number: 'C1', student_name: 'S', course_name: 'C', issued_at: '' } })
    const wrapper = await mountView()
    await wrapper.find('[data-testid="validate-code-input"]').setValue('CODE1')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(true)

    // Second: not found
    validateCertificate.mockRejectedValue({ response: { status: 404 } })
    await wrapper.find('[data-testid="validate-code-input"]').setValue('CODE2')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    // Valid state should be gone, invalid should show
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="validate-invalid"]').exists()).toBe(true)
  })
})
