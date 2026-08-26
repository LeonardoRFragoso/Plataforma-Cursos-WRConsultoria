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
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/validar-certificado', component: { template: '<div>validate</div>' } },
    ],
  })
  return router
}

async function mountView(query = {}) {
  const router = setupRouter()
  await router.push({ path: '/validar-certificado', query })
  await router.isReady()
  return mount(ValidateCertificate, { global: { plugins: [router] } })
}

function enrichedPayload(overrides = {}) {
  return {
    valid: true,
    status: 'ACTIVE',
    is_demo: false,
    certificate: {
      number: 'CERT-ABC123',
      validation_code: 'VCODE123',
      version: 1,
      issued_at: '2026-08-15T10:00:00Z',
      expires_at: null,
      content_hash: 'a'.repeat(64),
    },
    student: { name: 'João Silva' },
    course: {
      code: 'NR-01-F',
      name: 'Formação CIPA',
      category: 'Segurança',
      workload_hours: 8,
      modality: 'EAD',
    },
    journey: {
      progress: { required_lessons_total: 3, required_lessons_completed: 3, completion_percent: 100.0 },
      steps: [
        { type: 'ENROLLED', label: 'Matrícula confirmada', occurred_at: '2026-08-10T10:00:00Z', order: 1 },
        { type: 'COURSE_STARTED', label: 'Curso iniciado', occurred_at: '2026-08-11T10:00:00Z', order: 2 },
        { type: 'COURSE_COMPLETED', label: 'Curso concluído', occurred_at: '2026-08-15T10:00:00Z', order: 4 },
        { type: 'CERTIFICATE_ISSUED', label: 'Certificado emitido', occurred_at: '2026-08-15T10:00:00Z', order: 5 },
      ],
      lessons: [
        { type: 'LESSON_COMPLETED', label: 'Aula concluída: Aula 1', occurred_at: '2026-08-11T10:00:00Z', order: 0 },
      ],
    },
    // backwards-compatible flat fields
    certificate_number: 'CERT-ABC123',
    validation_code: 'VCODE123',
    version: 1,
    student_name: 'João Silva',
    course_name: 'Formação CIPA',
    issued_at: '2026-08-15T10:00:00Z',
    expires_at: null,
    content_hash: 'a'.repeat(64),
    ...overrides,
  }
}

describe('ValidateCertificate — QR auto-validation & enriched result', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    validateCertificate.mockReset()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('auto-validates from ?codigo= query param on mount', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    expect(validateCertificate).toHaveBeenCalledWith('VCODE123')
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="validate-code-input"]').element.value).toBe('VCODE123')
  })

  it('auto-validates from ?code= query param (backwards compat)', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    await mountView({ code: 'LEGACY-CODE' })
    await flushPromises()
    expect(validateCertificate).toHaveBeenCalledWith('LEGACY-CODE')
  })

  it('does not auto-validate when no query param present', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    await mountView()
    await flushPromises()
    expect(validateCertificate).not.toHaveBeenCalled()
  })

  it('renders course details (code, workload, modality, category)', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('NR-01-F')
    expect(text).toContain('8h')
    expect(text).toContain('EAD')
    expect(text).toContain('Segurança')
  })

  it('renders the academic journey timeline', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-journey"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="journey-step-ENROLLED"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="journey-step-COURSE_COMPLETED"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="journey-step-CERTIFICATE_ISSUED"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('3 de 3 aulas obrigatórias')
  })

  it('expands per-lesson detail on demand', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-lessons-list"]').exists()).toBe(false)
    await wrapper.find('[data-testid="validate-toggle-lessons"]').trigger('click')
    expect(wrapper.find('[data-testid="validate-lessons-list"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Aula concluída: Aula 1')
  })

  it('shows integrity section and technical details on demand', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-integrity"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Integridade digital verificada')
    expect(wrapper.find('[data-testid="validate-tech-details"]').exists()).toBe(false)
    await wrapper.find('[data-testid="validate-toggle-tech"]').trigger('click')
    expect(wrapper.find('[data-testid="validate-tech-details"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Hash do registro')
    expect(wrapper.text()).toContain('não do arquivo PDF')
  })

  it('shows demo banner and demo-specific valid label when is_demo=true', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload({ is_demo: true }) })
    const wrapper = await mountView({ codigo: 'DEMO-CODE' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-demo-banner"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Certificado de demonstração')
    expect(wrapper.text()).toContain('Não possui validade oficial')
    expect(wrapper.text()).toContain('Registro de demonstração válido')
    // Must NOT say "Certificado válido" (official wording) for demo
    const validCard = wrapper.find('[data-testid="validate-valid"]')
    expect(validCard.text()).not.toContain('Certificado válido')
  })

  it('does not show demo banner for official certificates', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload({ is_demo: false }) })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-demo-banner"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Certificado válido')
  })

  it('renders EXPIRED status distinctly', async () => {
    validateCertificate.mockResolvedValue({
      data: enrichedPayload({ valid: false, status: 'EXPIRED', expires_at: '2025-01-01T00:00:00Z' }),
    })
    const wrapper = await mountView({ codigo: 'EXP' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-expired"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Certificado expirado')
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(false)
  })

  it('renders REVOKED status with reason', async () => {
    validateCertificate.mockResolvedValue({
      data: enrichedPayload({
        valid: false,
        status: 'REVOKED',
        revocation_reason: 'Fraude documentada',
      }),
    })
    const wrapper = await mountView({ codigo: 'REV' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-revoked"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Certificado revogado')
    expect(wrapper.text()).toContain('Fraude documentada')
  })

  it('renders SUPERSEDED status distinctly', async () => {
    validateCertificate.mockResolvedValue({
      data: enrichedPayload({ valid: false, status: 'SUPERSEDED' }),
    })
    const wrapper = await mountView({ codigo: 'SUP' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-superseded"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Certificado substituído')
  })

  it('renders NOT_FOUND status distinctly (not generic invalid)', async () => {
    validateCertificate.mockResolvedValue({
      data: { valid: false, status: 'NOT_FOUND', is_demo: false },
    })
    const wrapper = await mountView({ codigo: 'NOPE' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-invalid"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Certificado não encontrado')
  })

  it('does not render any private fields in the DOM (privacy)', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    const html = wrapper.html().toLowerCase()
    for (const forbidden of ['cpf', 'email', 'phone', 'telefone', 'user_id', 'student_id', 'enrollment_id', 'actor_id', 'password', 'payment']) {
      expect(html).not.toContain(forbidden)
    }
  })

  it('clears previous result and re-runs on manual submit', async () => {
    validateCertificate.mockResolvedValue({ data: enrichedPayload() })
    const wrapper = await mountView({ codigo: 'VCODE123' })
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(true)

    validateCertificate.mockResolvedValue({ data: { valid: false, status: 'NOT_FOUND' } })
    await wrapper.find('[data-testid="validate-code-input"]').setValue('NEWCODE')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('[data-testid="validate-valid"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="validate-invalid"]').exists()).toBe(true)
  })
})
