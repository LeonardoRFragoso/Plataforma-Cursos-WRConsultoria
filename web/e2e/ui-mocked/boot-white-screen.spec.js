/* eslint-disable */
import { test, expect } from '@playwright/test'

// P0 white-screen regression: verifies that the app shows visible content
// quickly even when the API is slow/unavailable, and that a stale token
// on a public route does not produce a prolonged blank page.

const API_BASE = 'http://localhost:8000'

test.beforeEach(async ({ page }) => {
  // Mock tenant branding so the layout doesn't depend on a live API
  await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        name: 'WR Consultoria',
        logo_url: null,
        primary_color: '#047F37',
        secondary_color: '#17324D',
      }),
    })
  )
})

test('boot: página pública / mostra conteúdo visual rapidamente mesmo com API lenta', async ({ page }) => {
  // Delay /auth/me by 5s to simulate a slow backend. The app must NOT
  // stay blank for 5s — the boot state or public content should appear
  // within a couple of seconds.
  await page.route(`${API_BASE}/api/v1/auth/me`, async (route) => {
    await new Promise((r) => setTimeout(r, 5000))
    return route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Unauthorized"}' })
  })

  // No stale token — clean browser
  await page.goto('/')
  await page.waitForLoadState('commit')

  // Within 3s, #app must have visible content (boot spinner or Home)
  await page.waitForFunction(
    () => {
      const el = document.getElementById('app')
      if (!el) return false
      return el.children.length > 0 && el.offsetWidth > 0 && el.offsetHeight > 0
    },
    { timeout: 3000 }
  )

  // The page should not be a blank white screen
  const app = page.locator('#app')
  await expect(app).toBeVisible()
})

test('boot: token velho + rota pública / não provoca tela branca prolongada', async ({ page }) => {
  // Inject a stale token BEFORE the app loads
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'stale.invalid.token')
    localStorage.setItem('refresh_token', 'stale.invalid.refresh')
    localStorage.setItem('user_role', 'student')
  })

  // Delay /auth/me and /auth/refresh by 5s
  await page.route(`${API_BASE}/api/v1/auth/me`, async (route) => {
    await new Promise((r) => setTimeout(r, 5000))
    return route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Unauthorized"}' })
  })
  await page.route(`${API_BASE}/api/v1/auth/refresh`, async (route) => {
    await new Promise((r) => setTimeout(r, 5000))
    return route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Unauthorized"}' })
  })

  await page.goto('/')

  // Within 3s, #app must have visible content — NOT a 5s+ white screen
  await page.waitForFunction(
    () => {
      const el = document.getElementById('app')
      if (!el) return false
      return el.children.length > 0 && el.offsetWidth > 0 && el.offsetHeight > 0
    },
    { timeout: 3000 }
  )

  const app = page.locator('#app')
  await expect(app).toBeVisible()
})

test('boot: /login mostra conteúdo rapidamente mesmo com API lenta', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/auth/me`, async (route) => {
    await new Promise((r) => setTimeout(r, 5000))
    return route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Unauthorized"}' })
  })

  await page.goto('/login')

  // Login form should appear within 3s, not wait for the 5s API delay
  await page.waitForFunction(
    () => {
      const el = document.getElementById('app')
      if (!el) return false
      const text = (el.innerText || '').toLowerCase()
      return text.includes('entrar') || text.includes('login') || text.includes('e-mail') || text.includes('senha')
    },
    { timeout: 3000 }
  )
})

test('boot: boot state (spinner) aparece no HTML antes do JS carregar', async ({ page }) => {
  // This test verifies the inline boot state in index.html renders before
  // the JS bundle executes. We check the initial HTML content.
  const response = await page.goto('/')
  const html = await response.text()
  // The boot state should be present in the initial HTML
  expect(html).toContain('app-boot')
  expect(html).toContain('Carregando')
})
