/* eslint-disable */
import { test, expect } from '@playwright/test'

/**
 * White Label CEO Demo — UI mocked tests.
 *
 * Verifies that the frontend correctly:
 * 1. Displays WR branding when tenant slug resolves to "wr"
 * 2. Displays Alfa branding when tenant slug resolves to "alfa"
 * 3. Sends X-Tenant-Slug header on API requests
 * 4. Applies tenant primary color to CSS variables
 * 5. Shows tenant name in footer (no WR hardcoded leakage)
 */

const API_BASE = 'http://localhost:8000'

const WR_BRANDING = {
  name: 'WR Consultoria e Soluções',
  logo_url: null,
  logo_white_url: null,
  favicon_url: null,
  primary_color: '#0056b3',
  secondary_color: '#1a1a1a',
  accent_color: '#ff6b35',
}

const ALFA_BRANDING = {
  name: 'Alfa Academy',
  logo_url: 'https://example.com/alfa-logo.png',
  logo_white_url: null,
  favicon_url: 'https://example.com/alfa-favicon.ico',
  primary_color: '#E86A17',
  secondary_color: '#1F2937',
  accent_color: '#FBBF24',
}

test.describe('White Label — WR tenant', () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(WR_BRANDING),
      })
    )
    await page.route(`${API_BASE}/api/v1/courses`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'c1', code: 'NR-10', name: 'NR-10 Segurança', category: 'Seg', price: 250, is_active: true },
        ]),
      })
    )
  })

  test('displays WR tenant name and primary color', async ({ page }) => {
    await page.goto('/')
    // Wait for branding to load — tenant name appears in hero subtitle
    await expect(page.getByText('Plataforma de cursos da WR Consultoria e Soluções')).toBeVisible({ timeout: 10000 })
    // Primary color applied to CSS variable
    const primaryColor = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()
    )
    expect(primaryColor).toBe('#0056b3')
  })

  test('footer shows tenant name, not hardcoded WR', async ({ page }) => {
    await page.goto('/')
    const footer = page.locator('footer')
    await expect(footer).toContainText('WR Consultoria e Soluções')
    // Must NOT contain the old hardcoded text
    await expect(footer).not.toContainText('© 2026 WR Consultoria.')
  })
})

test.describe('White Label — Alfa tenant', () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ALFA_BRANDING),
      })
    )
    await page.route(`${API_BASE}/api/v1/courses`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'c2', code: 'SEG-01', name: 'Integração de Segurança', category: 'Eng', price: 400, is_active: true },
        ]),
      })
    )
  })

  test('displays Alfa tenant name and primary color', async ({ page }) => {
    await page.goto('/')
    // Wait for branding to load — tenant name appears in hero subtitle
    await expect(page.getByText('Plataforma de cursos da Alfa Academy')).toBeVisible({ timeout: 10000 })
    // Must NOT show WR branding
    await expect(page.getByText('WR Consultoria')).not.toBeVisible()

    const primaryColor = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()
    )
    expect(primaryColor).toBe('#E86A17')
  })

  test('applies Alfa favicon dynamically', async ({ page }) => {
    await page.goto('/')
    // Wait for favicon to be applied
    await page.waitForTimeout(500)
    const faviconHref = await page.evaluate(() => {
      const link = document.querySelector("link[rel~='icon']")
      return link ? link.href : null
    })
    expect(faviconHref).toContain('alfa-favicon.ico')
  })
})

test.describe('White Label — X-Tenant-Slug header', () => {
  test('API requests include X-Tenant-Slug header', async ({ page }) => {
    let capturedSlug = null

    await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) => {
      const headers = route.request().headers()
      capturedSlug = headers['x-tenant-slug']
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(WR_BRANDING),
      })
    })

    await page.goto('/')
    await page.waitForTimeout(500)
    // The branding request should have X-Tenant-Slug header
    expect(capturedSlug).toBeTruthy()
  })
})

test.describe('White Label — Validate Certificate page', () => {
  test('footer shows tenant name, not hardcoded WR', async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ALFA_BRANDING),
      })
    )

    await page.goto('/validar-certificado')
    const footer = page.locator('footer')
    await expect(footer).toContainText('Alfa Academy')
    await expect(footer).not.toContainText('WR Consultoria')
  })
})
