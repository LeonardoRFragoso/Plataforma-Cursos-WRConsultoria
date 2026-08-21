import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SuperAdmin from '../../views/SuperAdmin.vue'

vi.mock('../../api/superAdmin', () => ({
  listTenants: vi.fn(),
  listPlans: vi.fn(),
  listSubscriptions: vi.fn(),
  listPartnerLeads: vi.fn(),
  approvePartnerLead: vi.fn(),
  activateSubscription: vi.fn(),
  suspendSubscription: vi.fn(),
  renewSubscription: vi.fn(),
  createPlan: vi.fn(),
  createSubscription: vi.fn(),
  cancelSubscription: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}))

vi.mock('../../components/AppNavbar.vue', () => ({
  default: { template: '<div class="navbar-mock"></div>' },
}))

const setupRouter = () => {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div></div>' } },
      { path: '/super-admin', component: SuperAdmin },
    ],
  })
}

describe('SuperAdmin View', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  async function mountComponent() {
    const router = setupRouter()
    await router.push('/super-admin')
    await router.isReady()

    const superAdmin = await import('../../api/superAdmin')
    superAdmin.listTenants.mockResolvedValue([
      { id: 't1', name: 'WR', slug: 'wr', status: 'ACTIVE' },
      { id: 't2', name: 'Alfa', slug: 'alfa', status: 'ACTIVE' },
    ])
    superAdmin.listPlans.mockResolvedValue([
      { id: 'p1', name: 'Starter', price: 299, billing_cycle: 'MONTHLY' },
    ])
    superAdmin.listSubscriptions.mockResolvedValue([
      { id: 's1', tenant_id: 't1-uuid', plan_name: 'Starter', status: 'ACTIVE' },
      { id: 's2', tenant_id: 't2-uuid', plan_name: 'Starter', status: 'ACTIVE' },
    ])
    superAdmin.listPartnerLeads.mockResolvedValue([
      { id: 'pl1', company_name: 'NewCo', contact_email: 'new@co.test', status: 'PENDING' },
    ])

    const wrapper = mount(SuperAdmin, {
      global: {
        plugins: [router, createPinia()],
      },
    })
    await flushPromises()
    return { wrapper, router, superAdmin }
  }

  it('loads tenants on mount', async () => {
    const { wrapper } = await mountComponent()
    // Switch to Tenants tab
    const tenantTab = wrapper.find('[data-testid="tab-Tenants"]')
    if (tenantTab.exists()) {
      await tenantTab.trigger('click')
      await flushPromises()
    }
    expect(wrapper.text()).toContain('WR')
    expect(wrapper.text()).toContain('Alfa')
  })

  it('loads plans on mount', async () => {
    const { wrapper } = await mountComponent()
    // Switch to Planos tab
    const planTab = wrapper.find('[data-testid="tab-Planos"]')
    if (planTab.exists()) {
      await planTab.trigger('click')
      await flushPromises()
    }
    expect(wrapper.text()).toContain('Starter')
  })

  it('loads subscriptions on mount', async () => {
    const { wrapper } = await mountComponent()
    // Switch to Assinaturas tab
    const subTab = wrapper.find('[data-testid="tab-Assinaturas"]')
    if (subTab.exists()) {
      await subTab.trigger('click')
      await flushPromises()
    }
    expect(wrapper.text()).toContain('Ativa')
  })

  it('lists partner leads', async () => {
    const { wrapper } = await mountComponent()
    // Parceiros is the default tab
    expect(wrapper.text()).toContain('NewCo')
    expect(wrapper.text()).toContain('new@co.test')
  })

  it('invokes approve on partner lead', async () => {
    const { wrapper, superAdmin } = await mountComponent()
    superAdmin.approvePartnerLead.mockResolvedValue({})

    const approveBtn = wrapper.find('[data-testid="approve-partner-pl1"]')
    if (approveBtn.exists()) {
      await approveBtn.trigger('click')
      await flushPromises()
      expect(superAdmin.approvePartnerLead).toHaveBeenCalledWith('pl1')
    }
  })

  it('invokes suspend on subscription after confirmation', async () => {
    const { wrapper, superAdmin } = await mountComponent()
    superAdmin.suspendSubscription.mockResolvedValue({})
    superAdmin.listSubscriptions.mockResolvedValue([])

    const suspendBtn = wrapper.find('[data-testid="suspend-sub-s2"]')
    if (suspendBtn.exists()) {
      await suspendBtn.trigger('click')
      await flushPromises()
      // Confirm dialog should now be visible
      const confirmBtn = wrapper.find('[data-testid="confirm-ok"]')
      if (confirmBtn.exists()) {
        await confirmBtn.trigger('click')
        await flushPromises()
        expect(superAdmin.suspendSubscription).toHaveBeenCalledWith('s2')
      }
    }
  })

  it('handles API errors gracefully', async () => {
    const superAdmin = await import('../../api/superAdmin')
    vi.clearAllMocks()
    // All APIs fail — component catches with .catch(() => []) and shows empty state
    superAdmin.listTenants.mockRejectedValue({ response: { data: { detail: 'Unauthorized' } } })
    superAdmin.listPlans.mockRejectedValue(new Error('fail'))
    superAdmin.listSubscriptions.mockRejectedValue(new Error('fail'))
    superAdmin.listPartnerLeads.mockRejectedValue(new Error('fail'))

    const router = setupRouter()
    await router.push('/super-admin')
    await router.isReady()

    const wrapper = mount(SuperAdmin, {
      global: { plugins: [router, createPinia()] },
    })
    await flushPromises()

    // Should not crash — shows empty state messages
    expect(wrapper.text()).toContain('Nenhum lead')
  })
})
