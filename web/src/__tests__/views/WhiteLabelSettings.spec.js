import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import WhiteLabelSettings from '../../views/WhiteLabelSettings.vue'
import { useTenantStore } from '../../stores/tenant'

vi.mock('../../api/tenant', () => ({
  fetchTenantBranding: vi.fn(),
  updateTenantBranding: vi.fn(),
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
      { path: '/settings/white-label', component: WhiteLabelSettings },
    ],
  })
}

const brandingData = {
  name: 'Alfa Academy',
  logo_url: 'https://example.com/logo.png',
  logo_white_url: null,
  favicon_url: 'https://example.com/favicon.ico',
  primary_color: '#E86A17',
  secondary_color: '#1F2937',
  accent_color: '#FBBF24',
}

describe('WhiteLabelSettings View', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  let pinia

  async function mountComponent() {
    // Set up tenant store BEFORE mounting so the component reads it
    const tenantStore = useTenantStore()
    tenantStore.name = brandingData.name
    tenantStore.logo_url = brandingData.logo_url
    tenantStore.logo_white_url = brandingData.logo_white_url
    tenantStore.favicon_url = brandingData.favicon_url
    tenantStore.primary_color = brandingData.primary_color
    tenantStore.secondary_color = brandingData.secondary_color
    tenantStore.accent_color = brandingData.accent_color

    const router = setupRouter()
    await router.push('/settings/white-label')
    await router.isReady()

    const wrapper = mount(WhiteLabelSettings, {
      global: {
        plugins: [router, pinia],
      },
    })
    await flushPromises()
    return { wrapper, tenantStore, router }
  }

  it('loads current branding into form fields', async () => {
    const { wrapper } = await mountComponent()
    // First text input is the name field
    const textInputs = wrapper.findAll('input[type="text"]')
    const nameInput = textInputs[0]
    expect(nameInput.element.value).toBe('Alfa Academy')
    // First URL input is the logo field
    const urlInputs = wrapper.findAll('input[type="url"]')
    expect(urlInputs[0].element.value).toBe('https://example.com/logo.png')
  })

  it('shows color pickers with current values', async () => {
    const { wrapper } = await mountComponent()
    const colorInputs = wrapper.findAll('input[type="color"]')
    expect(colorInputs).toHaveLength(3)
    // Color inputs normalize to lowercase
    expect(colorInputs[0].element.value.toLowerCase()).toBe('#e86a17')
    expect(colorInputs[1].element.value.toLowerCase()).toBe('#1f2937')
    expect(colorInputs[2].element.value.toLowerCase()).toBe('#fbbf24')
  })

  it('saves branding through tenant API', async () => {
    const { updateTenantBranding } = await import('../../api/tenant')
    updateTenantBranding.mockResolvedValue({})
    const { wrapper } = await mountComponent()

    // Change name (first text input)
    const textInputs = wrapper.findAll('input[type="text"]')
    await textInputs[0].setValue('Alfa Academy Updated')

    // Submit
    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(updateTenantBranding).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Alfa Academy Updated' })
    )
  })

  it('reloads tenant store after save', async () => {
    const { updateTenantBranding, fetchTenantBranding } = await import('../../api/tenant')
    updateTenantBranding.mockResolvedValue({})
    fetchTenantBranding.mockResolvedValue(brandingData)
    const { wrapper, tenantStore } = await mountComponent()

    const spy = vi.spyOn(tenantStore, 'refreshBranding')
    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(spy).toHaveBeenCalled()
  })

  it('shows success message after save', async () => {
    const { updateTenantBranding } = await import('../../api/tenant')
    updateTenantBranding.mockResolvedValue({})
    const { wrapper } = await mountComponent()

    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('Branding atualizado com sucesso')
  })

  it('handles API failure with error message', async () => {
    const { updateTenantBranding } = await import('../../api/tenant')
    updateTenantBranding.mockRejectedValue({
      response: { data: { detail: 'Invalid color' } },
    })
    const { wrapper } = await mountComponent()

    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid color')
  })

  it('disables save button while saving', async () => {
    const { updateTenantBranding } = await import('../../api/tenant')
    updateTenantBranding.mockReturnValue(new Promise(() => {})) // never resolves
    const { wrapper } = await mountComponent()

    const form = wrapper.find('form')
    await form.trigger('submit.prevent')
    await flushPromises()

    const button = wrapper.find('button[type="submit"]')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toContain('Salvando')
  })
})
