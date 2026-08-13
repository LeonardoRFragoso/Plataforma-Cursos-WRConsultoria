import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Login from '../../views/Login.vue'

describe('Login Component', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: Login },
        { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
        { path: '/register', component: { template: '<div>Register</div>' } },
      ],
    })
  })

  it('renders login form', () => {
    const wrapper = mount(Login, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
  })

  it('has email and password inputs', () => {
    const wrapper = mount(Login, {
      global: {
        plugins: [router],
      },
    })

    const emailInput = wrapper.find('input[type="text"]')
    const passwordInput = wrapper.find('input[type="password"]')

    expect(emailInput.exists()).toBe(true)
    expect(passwordInput.exists()).toBe(true)
  })

  it('has register link', () => {
    const wrapper = mount(Login, {
      global: {
        plugins: [router],
      },
    })

    const registerLink = wrapper.find('a[href="/register"]')
    expect(registerLink.exists()).toBe(true)
  })

  it('displays error message when provided', async () => {
    const wrapper = mount(Login, {
      global: {
        plugins: [router],
      },
    })

    await wrapper.vm.$nextTick()
    wrapper.vm.error = 'Invalid credentials'
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Invalid credentials')
  })
})
