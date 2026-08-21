import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import PublicLayout from '../../layouts/PublicLayout.vue'

describe('PublicLayout', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders slot content and the public-layout marker', () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [] })
    const wrapper = mount(PublicLayout, {
      global: { plugins: [router] },
      slots: { default: '<div data-testid="public-content">hello</div>' },
    })
    expect(wrapper.find('[data-testid="public-layout"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="public-content"]').exists()).toBe(true)
  })

  it('does NOT render an authenticated app shell', () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [] })
    const wrapper = mount(PublicLayout, {
      global: { plugins: [router] },
      slots: { default: '<div>x</div>' },
    })
    expect(wrapper.find('[data-testid="app-shell"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="app-sidebar"]').exists()).toBe(false)
  })
})
