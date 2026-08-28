import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CourseProgressCard from '../../components/CourseProgressCard.vue'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn() },
}))

import api from '../../api/client'

const enrollment = {
  course_id: 'course-1',
  course_code: 'NR-35-F',
  course_name: 'NR 35 - Trabalho em Altura',
  course_category: 'NR 35',
  status: 'CONFIRMADA',
  start_date: '2026-08-01',
  end_date: '2026-08-31',
}

describe('CourseProgressCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue({
      data: { percentage: 0, completed_required: 0, required_lessons: 4 },
    })
  })

  it('usa capa 16:9 sem crop agressivo no card responsivo', async () => {
    const wrapper = mount(CourseProgressCard, {
      props: { enrollment },
      global: {
        stubs: {
          CourseCover: {
            name: 'CourseCover',
            props: ['course', 'ratio', 'fit', 'loading', 'wrapperClass'],
            template: '<div data-testid="course-cover-stub" :data-ratio="ratio" :data-fit="fit" :data-wrapper="wrapperClass" />',
          },
          ProgressBar: { template: '<div />' },
          StatusBadge: { template: '<div />' },
          RouterLink: {
            props: ['to'],
            template: '<a><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    const cover = wrapper.find('[data-testid="course-cover-stub"]')
    expect(cover.attributes('data-ratio')).toBe('16/9')
    expect(cover.attributes('data-fit')).toBe('contain')
    expect(cover.attributes('data-wrapper')).toContain('w-28')
    expect(cover.attributes('data-wrapper')).toContain('sm:w-36')
    expect(cover.attributes('data-wrapper')).not.toContain('w-full')
    expect(cover.attributes('data-wrapper')).not.toContain('sm:h-32')
  })
})
