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

describe('CourseCatalog — WR tenant (API-driven)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    tenantSlugMock.value = 'wr'
  })

  // WR tenant now shows loading skeleton while API loads (no more showcase)
  it('shows loading skeleton while API loads', () => {
    fetchPublicCourses.mockReturnValue(new Promise(() => {})) // never resolves
    const wrapper = mountCatalog()
    expect(wrapper.find('[data-testid="catalog-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(false)
  })

  // API returns real courses — they are rendered
  it('renders real API courses', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'NR-10-B', name: 'NR 10 - Básico', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 150 },
        { id: 2, code: 'NR-35-F', name: 'NR 35 - Trabalho em Altura', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 200 },
      ],
    })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('NR 10 - Básico')
    expect(wrapper.text()).toContain('NR 35 - Trabalho em Altura')
    expect(wrapper.text()).toContain('Ver detalhes')
  })

  // API returns [] — empty state shown
  it('shows empty state when API returns empty array', async () => {
    fetchPublicCourses.mockResolvedValue({ data: [] })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="catalog-grid"]').exists()).toBe(false)
  })

  // API returns error — error state shown
  it('shows error state on API failure', async () => {
    fetchPublicCourses.mockRejectedValue(new Error('Network error'))
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.find('[data-testid="catalog-error"]').exists()).toBe(true)
  })

  // No showcase "Em breve" badges anymore
  it('does not show "Em breve" badges', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'NR-10-B', name: 'NR 10 - Básico', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 150 },
      ],
    })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.text()).not.toContain('Em breve')
    expect(wrapper.text()).not.toContain('Disponível em breve')
  })

  // Search filters courses
  it('search filters courses by name', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'NR-05-F', name: 'NR 5 - CIPA', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 150 },
        { id: 2, code: 'NR-10-B', name: 'NR 10 - Básico', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 200 },
      ],
    })
    const wrapper = mountCatalog()
    await flushPromises()

    const searchInput = wrapper.find('[data-testid="catalog-search"]')
    await searchInput.setValue('CIPA')
    await flushPromises()

    const cards = wrapper.findAll('[data-testid="catalog-grid"] > div')
    expect(cards.length).toBe(1)
    expect(cards[0].text()).toContain('CIPA')
  })

  // Category filter works
  it('category filter narrows courses', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'NR-05-F', name: 'NR 5 - CIPA', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 150 },
        { id: 2, code: 'PS-F', name: 'Primeiros Socorros', category: 'Saúde', carga_horaria: 8, modality: 'EAD', price: 200 },
      ],
    })
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

  // Inactive courses are filtered out
  it('filters out inactive courses', async () => {
    fetchPublicCourses.mockResolvedValue({
      data: [
        { id: 1, code: 'NR-10-B', name: 'NR 10 - Básico', category: 'Segurança', carga_horaria: 8, modality: 'EAD', price: 150, is_active: true },
        { id: 2, code: 'NR-10-R', name: 'NR 10 - Reciclagem', category: 'Segurança', carga_horaria: 4, modality: 'EAD', price: 80, is_active: false },
      ],
    })
    const wrapper = mountCatalog()
    await flushPromises()

    expect(wrapper.text()).toContain('NR 10 - Básico')
    expect(wrapper.text()).not.toContain('NR 10 - Reciclagem')
  })
})

describe('CourseCatalog — non-WR tenant', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    tenantSlugMock.value = 'alfa'
  })

  it('shows loading skeleton for non-WR tenant', () => {
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
    expect(wrapper.text()).not.toContain('Em breve')
  })
})
