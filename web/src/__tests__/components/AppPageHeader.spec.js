import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppPageHeader from '../../components/AppPageHeader.vue'

describe('AppPageHeader', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders title and description', () => {
    const wrapper = mount(AppPageHeader, {
      props: { title: 'Cursos', description: 'Gerencie o catálogo.' },
    })
    expect(wrapper.text()).toContain('Cursos')
    expect(wrapper.text()).toContain('Gerencie o catálogo.')
    expect(wrapper.find('[data-testid="app-page-header"]').exists()).toBe(true)
  })

  it('omits description paragraph when not provided', () => {
    const wrapper = mount(AppPageHeader, { props: { title: 'Only Title' } })
    expect(wrapper.text()).toContain('Only Title')
    expect(wrapper.find('p').exists()).toBe(false)
  })

  it('renders actions slot', () => {
    const wrapper = mount(AppPageHeader, {
      props: { title: 'Turmas' },
      slots: {
        actions: '<button data-testid="slot-action">Nova</button>',
      },
    })
    expect(wrapper.find('[data-testid="slot-action"]').exists()).toBe(true)
  })
})
