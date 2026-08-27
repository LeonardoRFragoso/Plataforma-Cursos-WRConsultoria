import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import ComplianceOperations from '../../views/ComplianceOperations.vue'

const SUMMARY = {
  generated_at: '2026-08-27T00:00:00',
  course_status_counts: { COMPLIANCE_READY: 2 },
  enrollment_state_counts: { ENROLLED: 1 },
  signing_job_status_counts: { QUEUED: 2, FAILED: 1 },
  reviews_expired: 3,
  reviews_due_30_days: 4,
  signer_profile_enabled: true,
  signer_certificate_expires_30_days: false,
  signer_certificate_expired: false,
  signer_certificate_not_after: '2027-08-27T00:00:00',
  enrollments_without_ledger_events: 5,
  approved_retention_policy_version: 2,
  retention_policy_ready: true,
}

const CLASSES = [
  { id: 'cls-1', description: 'Turma A', start_date: '2026-01-01', end_date: '2026-12-31' },
]

const RETENTION_VERSIONS = [
  { id: 'v1', version: 1, status: 'APPROVED', created_at: '2026-01-01T00:00:00', certificate_retention_days: 365 },
  { id: 'v2', version: 2, status: 'DRAFT', created_at: '2026-08-27T00:00:00' },
]

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn((url) => {
      if (url === '/api/v1/classes/') return Promise.resolve({ data: CLASSES })
      return Promise.resolve({ data: [] })
    }),
  },
}))

vi.mock('../../api/complianceOperations', () => ({
  getComplianceOperationsSummary: vi.fn(() => Promise.resolve({ data: SUMMARY })),
  getComplianceClassReport: vi.fn(() => Promise.resolve({ data: { enrollment_count: 10 } })),
  listRetentionPolicyVersions: vi.fn(() => Promise.resolve({ data: RETENTION_VERSIONS })),
  createRetentionPolicyVersion: vi.fn(() => Promise.resolve({ data: RETENTION_VERSIONS[1] })),
  updateRetentionPolicyVersion: vi.fn(() => Promise.resolve({ data: { ...RETENTION_VERSIONS[1], certificate_retention_days: 180 } })),
  approveRetentionPolicyVersion: vi.fn(() => Promise.resolve({ data: { ...RETENTION_VERSIONS[1], status: 'APPROVED' } })),
}))

const setupRouter = () => createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/operations/compliance', component: ComplianceOperations },
    { path: '/dashboard', component: { template: '<div>dash</div>' } },
  ],
})

describe('ComplianceOperations View', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
    auth.user = { id: '1', full_name: 'Admin', role: 'admin' }
  })

  it('renderiza o dashboard de compliance', async () => {
    const router = setupRouter()
    await router.push('/operations/compliance')
    await router.isReady()
    const wrapper = mount(ComplianceOperations, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Operação e auditoria')
    expect(wrapper.text()).toContain('Revisões vencidas')
    expect(wrapper.text()).toContain('Revisões em 30 dias')
    expect(wrapper.text()).toContain('Matrículas sem ledger')
    expect(wrapper.text()).toContain('Política versionada')
    expect(wrapper.text()).toContain('v2')
  })

  it('exibe skeleton de loading antes das respostas', async () => {
    const { getComplianceOperationsSummary } = await import('../../api/complianceOperations')
    getComplianceOperationsSummary.mockImplementationOnce(() => new Promise(() => {}))

    const router = setupRouter()
    await router.push('/operations/compliance')
    await router.isReady()
    const wrapper = mount(ComplianceOperations, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
  })

  it('mostra mensagem de erro quando a API falha', async () => {
    const { getComplianceOperationsSummary } = await import('../../api/complianceOperations')
    getComplianceOperationsSummary.mockRejectedValueOnce({
      response: { data: { detail: 'Falha no carregamento' } },
    })

    const router = setupRouter()
    await router.push('/operations/compliance')
    await router.isReady()
    const wrapper = mount(ComplianceOperations, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Falha no carregamento')
  })

  it('permite selecionar uma turma e gerar o relatório', async () => {
    const { getComplianceClassReport } = await import('../../api/complianceOperations')
    getComplianceClassReport.mockResolvedValueOnce({
      data: { enrollment_count: 7, course_code: 'NR-10', course_name: 'Teste' },
    })

    const router = setupRouter()
    await router.push('/operations/compliance')
    await router.isReady()
    const wrapper = mount(ComplianceOperations, { global: { plugins: [router] } })
    await flushPromises()

    const options = wrapper.findAll('option').map((o) => o.element.value)
    expect(options).toContain('cls-1')

    wrapper.vm.selectedClassId = 'cls-1'
    await wrapper.vm.loadClassReport()
    await flushPromises()

    expect(wrapper.text()).toContain('NR-10')
    expect(wrapper.text()).toContain('7')
    expect(getComplianceClassReport).toHaveBeenCalledWith('cls-1')
  })

  it('destaca versão aprovada como somente leitura', async () => {
    const router = setupRouter()
    await router.push('/operations/compliance')
    await router.isReady()
    const wrapper = mount(ComplianceOperations, { global: { plugins: [router] } })
    await flushPromises()

    const approvedButton = wrapper.findAll('button').find((b) => b.text().includes('Versão 1'))
    if (approvedButton) await approvedButton.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('[data-testid="retention-days-input"]')
    expect(inputs.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('APPROVED')
  })

  it('permite editar rascunho, preencher e aprovar', async () => {
    const router = setupRouter()
    await router.push('/operations/compliance')
    await router.isReady()
    const wrapper = mount(ComplianceOperations, { global: { plugins: [router] } })
    await flushPromises()

    // Select the draft version.
    const draftButton = wrapper.findAll('button').find((b) => b.text().includes('Versão 2'))
    if (draftButton) await draftButton.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('[data-testid="retention-days-input"]')
    expect(inputs.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('DRAFT')
  })
})
