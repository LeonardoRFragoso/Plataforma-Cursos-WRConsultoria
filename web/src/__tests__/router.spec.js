import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../stores/auth'
import { navigationGuard, routes } from '../router/index.js'
import { createRouter, createMemoryHistory } from 'vue-router'

describe('Navigation guards', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = null
    auth.userRole = null
    auth.user = null
    auth.initialized = true

    router = createRouter({
      history: createMemoryHistory(),
      routes,
    })
    router.beforeEach(navigationGuard)
  })

  it('redireciona para /login quando rota exige auth sem token', async () => {
    await router.push('/dashboard')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('preserva intended path em redirect query ao exigir auth sem token', async () => {
    await router.push('/certificates')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/certificates')
  })

  it('preserva intended fullPath com params em redirect query', async () => {
    await router.push('/courses/course-123/learn')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/courses/course-123/learn')
  })

  it('mantém formulário de treinamento corporativo como rota pública', async () => {
    await router.push('/treinamentos-para-empresas')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/treinamentos-para-empresas')
  })

  it('redireciona aluno para /dashboard ao acessar rota admin', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/courses')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('impede aluno de acessar a central operacional', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/operations')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('permite admin acessar rota admin', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
    auth.user = { role: 'admin' }

    await router.push('/courses')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/courses')
  })

  it('permite admin acessar as filas operacionais', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
    auth.user = { role: 'admin' }

    await router.push('/operations/finance')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/operations/finance')
  })

  it('redireciona student para /dashboard ao acessar rota super_admin', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/super-admin')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('permite super_admin acessar rota super_admin', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'super_admin'
    auth.user = { role: 'super_admin' }

    await router.push('/super-admin')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/super-admin')
  })
})
