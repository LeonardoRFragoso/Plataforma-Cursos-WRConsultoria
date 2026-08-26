import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mock tenantSlug before importing CourseCatalog
const tenantSlugMock = vi.hoisted(() => ({ value: 'wr' }))
vi.mock('../../utils/tenantSlug', () => ({
  get TENANT_SLUG() {
    return tenantSlugMock.value
  },
}))

vi.mock('../../api/courses', () => ({
  fetchPublicCourses: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import CourseCatalog from '../../views/CourseCatalog.vue'
import { fetchPublicCourses } from '../../api/courses'

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Home</div>' } },
      { path: '/cursos', name: 'Catalog', component: CourseCatalog },
      { path: '/cursos/:id', component: { template: '<div>Curso</div>' } },
      { path: '/login', component: { template: '<div>Login</div>' } },
      { path: '/register', component: { template: '<div>Register</div>' } },
    ],
  })
}

function mountCatalog() {
  const router = createTestRouter()
  router.push('/cursos')
  return mount(CourseCatalog, {
    global: {
      plugins: [router],
    },
  })
}

describe('CourseCatalog — WR tenant showcase', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    tenantSlugMock.value = 'wr'
  })

  // Scenario 5: tenant WR — showcase visible immediately (before API resolves)
  it('renders WR showcase immediately without loading skeletons', () => {
    fetchPublicCourses.mockReturnValue(new Promise(() => {})) // never resolves
    const wrapper = mountCatalog()
    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="catalog-loading"]').exists()).toBe(false)
    // Showcase courses should be present
    const cards = wrapper.findAll('[data-testid="catalog-grid"] > div')
    expect(cards.length).toBeGreaterThan(0)
  })

  // Scenario 1: API returns real courses — showcase families deduplicated
  it('merges real API courses and removes showcase duplicates by family', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'NR-10-B', name: 'NR 10 - Básico', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 150 },
        { id: 2, code: 'NR-35-F', name: 'NR 35 - Trabalho em Altura', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 200 },
      ],
    })
    const wrapper = mountCatalog()
    await flushPromises()

    // Real courses should be present
    expect(wrapper.text()).toContain('NR 10 - Básico')
    expect(wrapper.text()).toContain('NR 35 - Trabalho em Altura')
    // Showcase NR-35 should NOT appear (deduplicated by family)
    const nr35Showcase = wrapper.findAll('[data-testid="catalog-grid"] > div').filter((c) =>
      c.text().includes('NR 35') && c.text().includes('Em breve')
    )
    expect(nr35Showcase.length).toBe(0)
    // Real courses should have "Ver detalhes", not "Em breve"
    expect(wrapper.text()).toContain('Ver detalhes')
  })

  // Scenario 2: API returns [] — showcase remains
  it('keeps showcase when API returns empty array', async () => {
    fetchPublicCourses.mockResolvedValue({ data: [] })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="catalog-empty"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="catalog-error"]').exists()).toBe(false)
    const cards = wrapper.findAll('[data-testid="catalog-grid"] > div')
    expect(cards.length).toBeGreaterThan(0)
  })

  // Scenario 3: API returns error — showcase remains, no error state
  it('keeps showcase on API error without showing error state', async () => {
    fetchPublicCourses.mockRejectedValue(new Error('Network error'))
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="catalog-error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="catalog-empty"]').exists()).toBe(false)
  })

  // Scenario 4: API demora indefinidamente — showcase stays, no skeleton
  it('does not show skeleton when API is slow (WR showcase already visible)', async () => {
    fetchPublicCourses.mockReturnValue(new Promise(() => {}))
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-loading"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(true)
  })

  // Scenario 9: duplicação por família — no duplicate NR-10
  it('does not produce duplicate courses for same family', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'NR-10-B', name: 'NR 10 - Básico', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 150 },
        { id: 2, code: 'NR-10-AE', name: 'NR 10 - SEP', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 200 },
      ],
    })
    const wrapper = mountCatalog()
    await flushPromises()

    // NR-10 family appears twice (both real), but no showcase NR-10
    const nr10Cards = wrapper.findAll('[data-testid="catalog-grid"] > div').filter((c) =>
      c.text().includes('NR-10') || c.text().includes('NR 10')
    )
    // Should have exactly 2 real NR-10 courses, no showcase duplicate
    const nr10Showcase = nr10Cards.filter((c) => c.text().includes('Em breve'))
    expect(nr10Showcase.length).toBe(0)
  })

  // Scenario 7: busca — search filters showcase courses
  it('search filters courses by name', async () => {
    fetchPublicCourses.mockResolvedValue({ data: [] })
    const wrapper = mountCatalog()
    await flushPromises()

    const searchInput = wrapper.find('[data-testid="catalog-search"]')
    await searchInput.setValue('CIPA')
    await flushPromises()

    const cards = wrapper.findAll('[data-testid="catalog-grid"] > div')
    expect(cards.length).toBe(1)
    expect(cards[0].text()).toContain('CIPA')
  })

  // Scenario 8: filtros — category filter works
  it('category filter narrows courses', async () => {
    fetchPublicCourses.mockResolvedValue({ data: [] })
    const wrapper = mountCatalog()
    await flushPromises()

    const saudeFilter = wrapper.find('[data-testid="catalog-filter-Saúde"]')
    await saudeFilter.trigger('click')
    await flushPromises()

    const cards = wrapper.findAll('[data-testid="catalog-grid"] > div')
    cards.forEach((card) => {
      expect(card.text()).toContain('Saúde')
    })
  })

  // Scenario 10: imagens dos cards — CourseCover renders for showcase
  it('renders course cards with cover images for showcase', () => {
    fetchPublicCourses.mockReturnValue(new Promise(() => {}))
    const wrapper = mountCatalog()

    // Showcase courses should have cover images (CourseCover component)
    const covers = wrapper.findAllComponents({ name: 'CourseCover' })
    expect(covers.length).toBeGreaterThan(0)
  })

  // Showcase courses show "Em breve", real courses show "Ver detalhes"
  it('showcase courses show "Em breve" badge and "Disponível em breve" button', async () => {
    fetchPublicCourses.mockResolvedValue({ data: [] })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.text()).toContain('Em breve')
    expect(wrapper.text()).toContain('Disponível em breve')
  })
})

describe('CourseCatalog — non-WR tenant', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    tenantSlugMock.value = 'alfa'
  })

  // Scenario 6: tenant não-WR — no showcase, normal loading
  it('shows loading skeleton for non-WR tenant (no showcase)', () => {
    fetchPublicCourses.mockReturnValue(new Promise(() => {}))
    const wrapper = mountCatalog()

    expect(wrapper.find('[data-testid="catalog-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(false)
  })

  it('shows error state on API failure for non-WR tenant', async () => {
    fetchPublicCourses.mockRejectedValue(new Error('Network error'))
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-error"]').exists()).toBe(true)
  })

  it('shows empty state when API returns [] for non-WR tenant', async () => {
    fetchPublicCourses.mockResolvedValue({ data: [] })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-empty"]').exists()).toBe(true)
  })

  it('renders real courses for non-WR tenant when API returns data', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'X-01', name: 'Course X', category: 'Cat', carga_horaria: 4, modality: 'EAD', price: 100 },
      ],
    })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Course X')
    // No showcase courses
    expect(wrapper.text()).not.toContain('Em breve')
  })
})
