/* eslint-disable */
import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:8000'

const BRANDING = {
  name: 'WR Consultoria',
  logo_url: null,
  logo_white_url: null,
  favicon_url: null,
  primary_color: '#1B7A3A',
  secondary_color: '#17324D',
  accent_color: '#F59E0B',
}

const COURSE = {
  id: 'premium-course-1',
  code: 'NR-10',
  name: 'NR-10 Segurança em Instalações Elétricas',
  category: 'Segurança',
  description: 'Treinamento profissional de segurança em eletricidade.',
  carga_horaria: 40,
  modality: 'EAD',
  price: 299.9,
  is_active: true,
}

test.beforeEach(async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BRANDING) })
  )
})

test('PREMIUM-UI-001: catálogo aplica branding e superfície premium', async ({ page }) => {
  await page.route('**/api/v1/courses/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([COURSE]) })
  )

  await page.goto('/cursos')

  await expect(page.getByTestId('catalog-header')).toBeVisible()
  await expect(page.getByTestId('catalog-grid')).toBeVisible()
  await expect(page.getByText(COURSE.name)).toBeVisible()
  await expect(page.getByTestId('catalog-search')).toBeVisible()

  const primary = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--brand-primary').trim().toLowerCase()
  )
  expect(primary).toBe(BRANDING.primary_color.toLowerCase())

  const cardRadius = await page.locator('[data-testid="catalog-grid"] article').first().evaluate((el) =>
    getComputedStyle(el).borderRadius
  )
  expect(parseFloat(cardRadius)).toBeGreaterThanOrEqual(12)
})

test('PREMIUM-UI-002: catálogo permanece utilizável em viewport mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/v1/courses/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([COURSE]) })
  )

  await page.goto('/cursos')
  await expect(page.getByText(COURSE.name)).toBeVisible()
  await expect(page.getByTestId('catalog-search')).toBeVisible()

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})

test('PREMIUM-UI-003: admin autenticado recebe shell e central operacional', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'premium-admin-token', refresh_token: 'premium-refresh', token_type: 'bearer' }),
    })
  )
  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 'admin-1', email: 'admin@example.com', full_name: 'Administrador WR', role: 'admin', is_active: true }),
    })
  )
  await page.route(`${API_BASE}/api/v1/dashboard/stats`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ totalStudents: 12, activeClasses: 3, pendingEnrollments: 2, monthlyRevenue: 599.8 }),
    })
  )

  await page.goto('/login')
  await page.fill('[data-testid="login-identifier"]', 'admin@example.com')
  await page.fill('[data-testid="login-password"]', 'password123')
  await page.click('button[type="submit"]')

  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByTestId('app-sidebar')).toBeVisible()
  await expect(page.getByTestId('app-topbar')).toBeVisible()
  await expect(page.getByTestId('nav-link-operations')).toBeVisible()
  await expect(page.getByText('Central operacional', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Receita do mês')).toBeVisible()
})
