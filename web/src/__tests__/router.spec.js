import { describe, it, expect, beforeEach, vi } from 'vitest'
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

  it('impede aluno de acessar o Certificate Studio', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/operations/certificate-studio')
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

  it('permite admin acessar o Certificate Studio', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
    auth.user = { role: 'admin' }

    await router.push('/operations/certificate-studio')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/operations/certificate-studio')
  })

  it('impede aluno de acessar a operação de Compliance NR', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'student'
    auth.user = { role: 'student' }

    await router.push('/operations/compliance')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('permite admin acessar a operação de Compliance NR', async () => {
    const auth = useAuthStore()
    auth.token = 'fake-token'
    auth.userRole = 'admin'
    auth.user = { role: 'admin' }

    await router.push('/operations/compliance')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/operations/compliance')
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

// ---------------------------------------------------------------------------
// P0 white-screen regression tests
//
// The original bug: the router guard awaited initializeUser() (→ /auth/me)
// for EVERY route when a token existed in localStorage. A slow/down API
// produced a 16+ second white screen even on public pages like / or /login.
// These tests verify that public routes never block on session restoration.
// ---------------------------------------------------------------------------

describe('P0 white-screen: public routes must not block on /auth/me', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createRouter({ history: createMemoryHistory(), routes })
    router.beforeEach(navigationGuard)
  })

  it('rota pública + sem token: não chama initializeUser', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.initialized = false
    const spy = vi.spyOn(auth, 'initializeUser')

    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/')
    expect(spy).not.toHaveBeenCalled()
  })

  it('rota pública + token velho: não bloqueia em initializeUser', async () => {
    const auth = useAuthStore()
    auth.token = 'stale-token'
    auth.initialized = false
    // initializeUser would block if called — we verify it is NOT called
    const spy = vi.spyOn(auth, 'initializeUser').mockResolvedValue()

    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/')
    expect(spy).not.toHaveBeenCalled()
  })

  it('rota pública /login + token velho: não bloqueia', async () => {
    const auth = useAuthStore()
    auth.token = 'stale-token'
    auth.initialized = false
    const spy = vi.spyOn(auth, 'initializeUser').mockResolvedValue()

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(spy).not.toHaveBeenCalled()
  })

  it('rota pública /validar-certificado + token velho: não bloqueia', async () => {
    const auth = useAuthStore()
    auth.token = 'stale-token'
    auth.initialized = false
    const spy = vi.spyOn(auth, 'initializeUser').mockResolvedValue()

    await router.push('/validar-certificado')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/validar-certificado')
    expect(spy).not.toHaveBeenCalled()
  })

  it('rota pública /cursos/:id + token velho: não bloqueia', async () => {
    const auth = useAuthStore()
    auth.token = 'stale-token'
    auth.initialized = false
    const spy = vi.spyOn(auth, 'initializeUser').mockResolvedValue()

    await router.push('/cursos/abc-123')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/cursos/abc-123')
    expect(spy).not.toHaveBeenCalled()
  })
})

describe('P0 white-screen: protected routes', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createRouter({ history: createMemoryHistory(), routes })
    router.beforeEach(navigationGuard)
  })

  it('rota protegida + sem token: redirect imediato para /login', async () => {
    const auth = useAuthStore()
    auth.token = null
    auth.initialized = false
    const spy = vi.spyOn(auth, 'initializeUser')

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(spy).not.toHaveBeenCalled()
  })

  it('rota protegida + token válido: inicializa sessão e permite', async () => {
    const auth = useAuthStore()
    auth.token = 'valid-token'
    auth.initialized = false
    const spy = vi.spyOn(auth, 'initializeUser').mockImplementation(() => {
      auth.user = { role: 'student' }
      auth.userRole = 'student'
      auth.initialized = true
      return Promise.resolve()
    })

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/dashboard')
    expect(spy).toHaveBeenCalled()
  })

  it('rota protegida + token inválido: limpa sessão e redireciona', async () => {
    const auth = useAuthStore()
    auth.token = 'invalid-token'
    auth.initialized = false
    // Simulate initializeUser failing and clearing the session (as the
    // interceptor would do on a 401 that can't be refreshed)
    const spy = vi.spyOn(auth, 'initializeUser').mockImplementation(() => {
      auth.token = null
      auth.user = null
      auth.userRole = null
      auth.initialized = true
      return Promise.resolve()
    })

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(spy).toHaveBeenCalled()
  })

  it('rota protegida admin + token válido admin: inicializa e permite', async () => {
    const auth = useAuthStore()
    auth.token = 'valid-admin-token'
    auth.initialized = false
    vi.spyOn(auth, 'initializeUser').mockImplementation(() => {
      auth.user = { role: 'admin' }
      auth.userRole = 'admin'
      auth.initialized = true
      return Promise.resolve()
    })

    await router.push('/operations/compliance')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/operations/compliance')
  })
})
