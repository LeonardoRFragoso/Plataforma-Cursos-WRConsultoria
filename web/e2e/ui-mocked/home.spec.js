/* eslint-disable */
import { test, expect } from '@playwright/test'

// Mock das respostas da API para tornar os testes e2e independentes do backend.
// Todos os testes interceptam as chamadas para http://localhost:8000 (API_URL default).

const API_BASE = 'http://localhost:8000'

test.beforeEach(async ({ page }) => {
  // Mock tenant branding
  await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        name: 'WR Consultoria',
        logo_url: null,
        primary_color: '#047F37',
        secondary_color: '#1a1a1a',
      }),
    })
  )
})

test('fluxo 1: página inicial carrega e exibe cursos disponíveis', async ({ page }) => {
  // fetchPublicCourses() requests /api/v1/courses/ (trailing slash) with
  // query params — use a glob so the mock matches the actual request URL.
  await page.route('**/api/v1/courses**', (route) => {
    // Only fulfill the list endpoint; let specific-course requests fall through.
    const url = route.request().url()
    if (url.includes('/api/v1/courses/') && !url.includes('?')) {
      return route.fallback()
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'course-1',
          code: 'NR-10',
          name: 'NR-10 Segurança em Instalações Elétricas',
          category: 'Segurança',
          price: 250.0,
          is_active: true,
        },
      ]),
    })
  })

  await page.goto('/')
  // WR tenant shows the hero artwork with a different headline
  await expect(page.locator('[data-testid="home-hero"]')).toBeVisible()
  await expect(page.locator('text=Cursos em destaque')).toBeVisible()
  await expect(page.locator('text=NR-10 Segurança em Instalações Elétricas')).toBeVisible()
})

test('fluxo 2: login de estudante redireciona para dashboard', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'fake-token-123',
        refresh_token: 'fake-refresh-123',
        token_type: 'bearer',
      }),
    })
  )

  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-1',
        email: 'student@test.com',
        full_name: 'Student Test',
        role: 'student',
      }),
    })
  )

  await page.goto('/login')
  await expect(page.locator('h1')).toBeVisible()

  await page.fill('input[placeholder*="CPF"]', 'student@test.com')
  await page.fill('input[type="password"]', 'password123')
  await page.click('button[type="submit"]')

  // Após login, redireciona para /dashboard
  await expect(page).toHaveURL(/\/dashboard/)
  // The user name appears in the sidebar, topbar, and profile card —
  // scope to the workspace to confirm the dashboard rendered for this user
  await expect(page.locator('[data-testid="app-workspace"]')).toContainText('Student Test')
})

test('fluxo 3: detalhe do curso mostra "Acessar curso" para matrícula concluída', async ({ page }) => {
  const courseId = 'course-concluded-1'

  await page.route(`${API_BASE}/api/v1/courses/${courseId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: courseId,
        code: 'NR-35',
        name: 'NR-35 Trabalho em Altura',
        category: 'Segurança',
        price: 180.0,
        is_active: true,
        description: 'Curso de trabalho em altura',
      }),
    })
  )

  await page.route(`${API_BASE}/api/v1/enrollments/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'enr-1',
          course_id: courseId,
          class_id: 'class-1',
          status: 'CONCLUIDA',
          price: 180.0,
        },
      ]),
    })
  )

  // Simula token de auth no localStorage
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'fake-token')
    localStorage.setItem('refresh_token', 'fake-refresh')
    localStorage.setItem('user_role', 'student')
  })

  // Mock auth/me para evitar redirect do interceptor 401
  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-1',
        email: 'student@test.com',
        full_name: 'Student Test',
        role: 'student',
      }),
    })
  )

  await page.goto(`/cursos/${courseId}`)
  await expect(page.locator('text=NR-35 Trabalho em Altura')).toBeVisible()
  // Para CONCLUIDA, o botão deve ser "Acessar curso", não "Comprar novamente"
  await expect(page.locator('text=Acessar curso')).toBeVisible()
  await expect(page.locator('text=Comprar novamente')).not.toBeVisible()
})

test('fluxo 4: validação de certificado com código válido', async ({ page }) => {
  const validCode = 'VALID-CODE-123'

  await page.route(`${API_BASE}/api/v1/certificates/validate`, (route) => {
    const request = route.request()
    const postData = request.postDataJSON()

    if (postData && postData.validation_code === validCode) {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          valid: true,
          certificate_number: 'CERT-2024-001',
          student_name: 'João da Silva',
          course_name: 'NR-10 Segurança em Instalações Elétricas',
          issued_at: '2024-06-15T10:00:00Z',
        }),
      })
    } else {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valid: false }),
      })
    }
  })

  await page.goto('/validar-certificado')
  await expect(page.locator('h1')).toContainText('Validar certificado')

  await page.fill('input[placeholder="Cole o código de validação aqui"]', validCode)
  await page.click('button[type="submit"]')

  await expect(page.locator('text=Certificado válido')).toBeVisible()
  await expect(page.locator('text=João da Silva')).toBeVisible()
  await expect(page.locator('text=NR-10 Segurança em Instalações Elétricas')).toBeVisible()
})
