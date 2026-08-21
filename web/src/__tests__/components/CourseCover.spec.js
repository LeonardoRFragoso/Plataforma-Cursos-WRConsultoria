import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

// Mock tenantSlug
vi.mock('../../utils/tenantSlug', () => ({
  TENANT_SLUG: 'wr',
}))

// Mock tenant store
vi.mock('../../stores/tenant', () => ({
  useTenantStore: () => ({
    primary_color: '#0056b3',
    secondary_color: '#1a1a1a',
    name: 'WR Cursos',
  }),
}))

import CourseCover from '../../components/CourseCover.vue'

describe('CourseCover.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders WR cover image for NR 10 course', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'NR 10', code: 'NR-10-B', name: 'NR 10 - Básico' },
      },
    })
    const img = wrapper.find('[data-testid="course-cover-img"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/assets/wr/courses/nr-10-eletricidade.webp')
    expect(img.attributes('alt')).toContain('NR-10')
  })

  it('renders fallback for unmapped course', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'Unknown', code: 'UNK-F', name: 'Unknown Course' },
      },
    })
    const fallback = wrapper.find('[data-testid="course-cover-fallback"]')
    expect(fallback.exists()).toBe(true)
    expect(fallback.text()).toContain('UNK-F')
  })

  it('uses lazy loading by default', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'NR 10', code: 'NR-10-B', name: 'NR 10' },
      },
    })
    expect(wrapper.props('loading')).toBe('lazy')
  })

  it('uses eager loading when specified', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'NR 10', code: 'NR-10-B', name: 'NR 10' },
        loading: 'eager',
      },
    })
    expect(wrapper.props('loading')).toBe('eager')
  })

  it('respects custom ratio', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'NR 10', code: 'NR-10-B', name: 'NR 10' },
        ratio: '21/9',
      },
    })
    expect(wrapper.props('ratio')).toBe('21/9')
  })

  it('renders backend-provided cover_image_url', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: {
          category: 'Custom',
          code: 'C-F',
          name: 'Custom Course',
          cover_image_url: 'https://example.com/custom.webp',
          cover_image_alt: 'Custom alt text',
        },
      },
    })
    const img = wrapper.find('[data-testid="course-cover-img"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('https://example.com/custom.webp')
    expect(img.attributes('alt')).toBe('Custom alt text')
  })

  it('falls back when image fails to load', async () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'NR 10', code: 'NR-10-B', name: 'NR 10' },
      },
    })
    const img = wrapper.find('[data-testid="course-cover-img"]')
    await img.trigger('error')
    const fallback = wrapper.find('[data-testid="course-cover-fallback"]')
    expect(fallback.exists()).toBe(true)
  })

  it('renders course code in fallback', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'Unknown', code: 'UNK-F', name: 'Unknown Course' },
      },
    })
    const fallback = wrapper.find('[data-testid="course-cover-fallback"]')
    expect(fallback.text()).toContain('UNK-F')
  })

  it('renders category in fallback', () => {
    const wrapper = mount(CourseCover, {
      props: {
        course: { category: 'Custom Cat', code: 'CC-F', name: 'Custom' },
      },
    })
    const fallback = wrapper.find('[data-testid="course-cover-fallback"]')
    expect(fallback.text()).toContain('Custom Cat')
  })
})
