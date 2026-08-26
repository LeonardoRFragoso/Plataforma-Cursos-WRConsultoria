/* eslint-disable */
import { test, expect } from '@playwright/test'

// B2C entry journey and multi-tenant identity E2E tests.
// All API calls are mocked — no real backend or Asaas credentials needed.

const API_BASE = 'http://localhost:8000'

const COURSE = {
  id: 'course-b2c-1',
  code: 'NR-10',
  name: 'NR-10 Segurança em Instalações Elétricas',
  category: 'Segurança',
  price: 250.0,
  is_active: true,
  description: 'Curso de segurança em instalações elétricas',
  carga_horaria: 40,
  modality: 'EAD',
  type: 'FORMACAO',
  prerequisite: null,
}

const STUDENT_ME = {
  id: 'user-b2c-1',
  email: 'b2c@example.com',
  full_name: 'B2C Student',
  role: 'student',
  cpf: '52998224725',
  is_active: true,
}

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

// ---------------------------------------------------------------------------
// B2C-ENTRY-001: anonymous visitor → course → register → auto-login → course
// ---------------------------------------------------------------------------

test('B2C-ENTRY-001: visitante anônimo → curso → cadastro → auto-login → retorna ao curso', async ({ page }) => {
  const courseId = COURSE.id

  // Mock course detail
  await page.route(`${API_BASE}/api/v1/courses/${courseId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(COURSE),
    })
  )

  // Mock registration — succeeds
  let registerCalled = false
  await page.route(`${API_BASE}/api/v1/auth/register`, (route) => {
    registerCalled = true
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...STUDENT_ME }),
    })
  })

  // Mock login — succeeds (auto-login after registration)
  await page.route(`${API_BASE}/api/v1/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'fake-token-b2c',
        refresh_token: 'fake-refresh-b2c',
        token_type: 'bearer',
      }),
    })
  )

  // Mock auth/me
  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(STUDENT_ME),
    })
  )

  // Mock enrollments (empty — no existing enrollment)
  await page.route(`${API_BASE}/api/v1/enrollments/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  )

  // 1. Visit the course detail page (anonymous)
  await page.goto(`/cursos/${courseId}`)
  await expect(page.locator('text=NR-10 Segurança em Instalações Elétricas')).toBeVisible()

  // 2. Click "Entrar para comprar"
  await expect(page.locator('button:has-text("Entrar para comprar")')).toBeVisible()
  await page.click('button:has-text("Entrar para comprar")')

  // 3. Should be on login page with redirect preserved
  await expect(page).toHaveURL(/\/login/)
  await expect(page).toHaveURL(/redirect=/)
  await expect(page.url()).toContain(courseId)

  // 4. Click "Cadastre-se" — redirect should be preserved
  await page.click('[data-testid="login-register-link"]')
  await expect(page).toHaveURL(/\/register/)

  // 5. Fill registration form
  await page.fill('[data-testid="register-fullname"]', 'B2C Student')
  await page.fill('[data-testid="register-email"]', 'b2c@example.com')
  await page.fill('[data-testid="register-cpf"]', '52998224725')
  await page.fill('[data-testid="register-password"]', 'password123')
  await page.fill('[data-testid="register-confirm"]', 'password123')

  // 6. Submit registration
  await page.click('button[type="submit"]')

  // 7. Auto-login should happen and redirect back to the course
  await expect(page).toHaveURL(new RegExp(`/cursos/${courseId}`))
  expect(registerCalled).toBe(true)

  // 8. The course detail should now show purchase options for authenticated student
  await expect(page.locator('text=NR-10 Segurança em Instalações Elétricas')).toBeVisible()
})

// ---------------------------------------------------------------------------
// B2C-ENTRY-002: existing user logs in and returns to course
// ---------------------------------------------------------------------------

test('B2C-ENTRY-002: usuário existente → curso → login → retorna ao curso', async ({ page }) => {
  const courseId = COURSE.id

  await page.route(`${API_BASE}/api/v1/courses/${courseId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(COURSE),
    })
  )

  await page.route(`${API_BASE}/api/v1/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'fake-token-returning',
        refresh_token: 'fake-refresh-returning',
        token_type: 'bearer',
      }),
    })
  )

  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(STUDENT_ME),
    })
  )

  await page.route(`${API_BASE}/api/v1/enrollments/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  )

  // 1. Visit course (anonymous)
  await page.goto(`/cursos/${courseId}`)
  await expect(page.locator('text=NR-10 Segurança em Instalações Elétricas')).toBeVisible()

  // 2. Click "Entrar para comprar"
  await page.click('button:has-text("Entrar para comprar")')

  // 3. Login page with redirect
  await expect(page).toHaveURL(/\/login/)
  await expect(page.url()).toContain(courseId)

  // 4. Login
  await page.fill('input[placeholder*="CPF"]', 'b2c@example.com')
  await page.fill('input[type="password"]', 'password123')
  await page.click('button[type="submit"]')

  // 5. Should return to the course
  await expect(page).toHaveURL(new RegExp(`/cursos/${courseId}`))
  await expect(page.locator('text=NR-10 Segurança em Instalações Elétricas')).toBeVisible()
})

// ---------------------------------------------------------------------------
// B2C-ENTRY-003: logout → login → redirect still works
// ---------------------------------------------------------------------------

test('B2C-ENTRY-003: logout → login → redirect ainda funciona', async ({ browser }) => {
  // Use a fresh browser context to simulate a clean session after logout
  const context = await browser.newContext()
  const page = await context.newPage()

  const courseId = COURSE.id

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

  await page.route(`${API_BASE}/api/v1/courses/${courseId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(COURSE),
    })
  )

  await page.route(`${API_BASE}/api/v1/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'fake-token-logout',
        refresh_token: 'fake-refresh-logout',
        token_type: 'bearer',
      }),
    })
  )

  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(STUDENT_ME),
    })
  )

  await page.route(`${API_BASE}/api/v1/enrollments/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  )

  // 1. Visit course (anonymous — fresh context, no localStorage)
  await page.goto(`/cursos/${courseId}`)
  await expect(page.locator('text=NR-10 Segurança em Instalações Elétricas')).toBeVisible()

  // 2. Click "Entrar para comprar"
  await expect(page.locator('button:has-text("Entrar para comprar")')).toBeVisible()
  await page.click('button:has-text("Entrar para comprar")')

  // 3. Login page with redirect
  await expect(page).toHaveURL(/\/login/)
  await expect(page.url()).toContain(courseId)

  // 4. Login
  await page.fill('input[placeholder*="CPF"]', 'b2c@example.com')
  await page.fill('input[type="password"]', 'password123')
  await page.click('button[type="submit"]')

  // 5. Should return to the course
  await expect(page).toHaveURL(new RegExp(`/cursos/${courseId}`))

  await context.close()
})

// ---------------------------------------------------------------------------
// MULTITENANT-ID-001: same identity in WR and Alfa — each tenant logs into its own account
// ---------------------------------------------------------------------------

test('MULTITENANT-ID-001: mesma identidade em WR e Alfa — cada tenant autentica seu próprio usuário', async ({ page }) => {
  // This test verifies the frontend behavior: the same email can be used
  // in both WR and Alfa contexts. The backend tenant-scoping is covered
  // by backend tests (test_b2c_identity_journeys.py).

  const sharedEmail = 'shared@example.com'

  // Mock login — succeeds for both tenants (backend handles tenant scoping)
  await page.route(`${API_BASE}/api/v1/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'fake-token-shared',
        refresh_token: 'fake-refresh-shared',
        token_type: 'bearer',
      }),
    })
  )

  // Mock auth/me — returns the user
  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-shared',
        email: sharedEmail,
        full_name: 'Shared User',
        role: 'student',
        cpf: '52998224725',
        is_active: true,
      }),
    })
  )

  // 1. Login in WR context
  await page.goto('/login')
  await page.fill('input[placeholder*="CPF"]', sharedEmail)
  await page.fill('input[type="password"]', 'password123')
  await page.click('button[type="submit"]')

  // 2. Should be authenticated and on dashboard
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.locator('[data-testid="app-workspace"]')).toContainText('Shared User')

  // 3. Logout
  await page.evaluate(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_role')
  })

  // 4. Login again with the same email (simulating Alfa context)
  await page.goto('/login')
  await page.fill('input[placeholder*="CPF"]', sharedEmail)
  await page.fill('input[type="password"]', 'password123')
  await page.click('button[type="submit"]')

  // 5. Should also authenticate successfully (same email, different tenant)
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.locator('[data-testid="app-workspace"]')).toContainText('Shared User')
})
