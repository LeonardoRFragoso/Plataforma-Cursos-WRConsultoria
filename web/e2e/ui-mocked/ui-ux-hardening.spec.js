/* eslint-disable */
import { test, expect } from '@playwright/test'

/**
 * UI/UX Hardening E2E — behavioral tests for the hardened UI.
 *
 * Covers: navigation, role matrix, responsive, accessibility, dialogs.
 * Uses mocked API (no backend required) — runs under the ui-mocked project.
 */

const API_BASE = 'http://localhost:8000'

// --- Helpers ---

async function mockTenantBranding(page, name = 'WR Consultoria') {
  await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        name,
        logo_url: null,
        primary_color: '#0056b3',
        secondary_color: '#1a1a1a',
      }),
    })
  )
}

async function mockAuth(page, role = 'student') {
  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-1',
        email: `${role}@test.com`,
        full_name: `${role} Test`,
        role,
      }),
    })
  )
}

async function setAuth(page, role = 'student') {
  await page.addInitScript((r) => {
    localStorage.setItem('access_token', 'fake-token')
    localStorage.setItem('refresh_token', 'fake-refresh')
    localStorage.setItem('user_role', r)
  }, role)
}

async function mockEmptyList(page, path) {
  await page.route(`${API_BASE}${path}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  )
}

// ============================================================
// 1. PUBLIC NAVIGATION
// ============================================================

test.describe('Public navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockTenantBranding(page)
  })

  test('Home renders with public nav links', async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/courses`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    )
    await page.goto('/')
    await expect(page.locator('[data-testid="home-nav-cursos"]')).toBeVisible()
    await expect(page.locator('[data-testid="home-nav-validar"]')).toBeVisible()
    await expect(page.locator('[data-testid="home-nav-parceiro"]')).toBeVisible()
    await expect(page.locator('[data-testid="home-nav-login"]')).toBeVisible()
    await expect(page.locator('[data-testid="home-nav-cadastro"]')).toBeVisible()
  })

  test('Cursos link navigates to /cursos', async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/courses`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    )
    await page.goto('/')
    await page.click('[data-testid="home-nav-cursos"]')
    await expect(page).toHaveURL(/\/cursos/)
  })

  test('Validar certificado link navigates to /validar-certificado', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="home-nav-validar"]')
    await expect(page).toHaveURL(/\/validar-certificado/)
  })

  test('Seja parceiro link navigates to /seja-parceiro', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="home-nav-parceiro"]')
    await expect(page).toHaveURL(/\/seja-parceiro/)
  })

  test('Login link navigates to /login', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="home-nav-login"]')
    await expect(page).toHaveURL(/\/login/)
  })

  test('protected routes redirect to login when unauthenticated', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
    await page.goto('/courses')
    await expect(page).toHaveURL(/\/login/)
    await page.goto('/super-admin')
    await expect(page).toHaveURL(/\/login/)
  })
})

// ============================================================
// 2. STUDENT NAVIGATION
// ============================================================

test.describe('Student navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
  })

  test('logo navigates to /dashboard', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.locator('[data-testid="navbar-logo"]')).toBeVisible()
    await page.click('[data-testid="navbar-logo"]')
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('shows Dashboard, Catálogo, Certificados — no duplication', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.locator('[data-testid="nav-link-dashboard"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-link-catalog"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-link-certificates"]')).toBeVisible()
    // No "Meus Cursos" link (removed)
    await expect(page.locator('[data-testid="nav-link-my-courses"]')).toHaveCount(0)
    // No admin links
    await expect(page.locator('[data-testid="nav-link-courses"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="nav-link-classes"]')).toHaveCount(0)
  })

  test('Catálogo navigates to /cursos', async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/courses`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    )
    await page.goto('/dashboard')
    await page.click('[data-testid="nav-link-catalog"]')
    await expect(page).toHaveURL(/\/cursos/)
  })

  test('admin routes denied for student', async ({ page }) => {
    await page.goto('/courses')
    // Should redirect to dashboard (home for student)
    await expect(page).toHaveURL(/\/dashboard/)
    await page.goto('/students')
    await expect(page).toHaveURL(/\/dashboard/)
    await page.goto('/super-admin')
    await expect(page).toHaveURL(/\/dashboard/)
  })
})

// ============================================================
// 3. ADMIN NAVIGATION
// ============================================================

test.describe('Admin navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'admin')
    await setAuth(page, 'admin')
    await mockEmptyList(page, '/api/v1/courses')
    await mockEmptyList(page, '/api/v1/classes')
    await mockEmptyList(page, '/api/v1/students')
    await mockEmptyList(page, '/api/v1/enrollments')
    await mockEmptyList(page, '/api/v1/payments')
    await mockEmptyList(page, '/api/v1/certificates')
  })

  test('logo navigates to /dashboard', async ({ page }) => {
    await page.goto('/dashboard')
    await page.click('[data-testid="navbar-logo"]')
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('shows Dashboard + Gestão dropdown with admin links', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page.locator('[data-testid="nav-link-dashboard"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-group-management"]')).toBeVisible()
  })

  test('Gestão group expands on click and shows admin links', async ({ page }) => {
    await page.goto('/dashboard')
    // Group is collapsed by default when the active route is not inside it
    await page.click('[data-testid="nav-group-management"]')
    await expect(page.locator('[data-testid="nav-group-panel-management"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-link-courses"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-link-classes"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-link-students"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-link-enrollments"]')).toBeVisible()
    await expect(page.locator('[data-testid="nav-link-payments"]')).toBeVisible()
  })

  test('Cursos in group navigates to /courses', async ({ page }) => {
    await page.goto('/dashboard')
    await page.click('[data-testid="nav-group-management"]')
    await expect(page.locator('[data-testid="nav-link-courses"]')).toBeVisible()
    await page.click('[data-testid="nav-link-courses"]')
    await expect(page).toHaveURL(/\/courses/)
  })

  test('super-admin route denied for admin', async ({ page }) => {
    await page.goto('/super-admin')
    await expect(page).toHaveURL(/\/dashboard/)
  })
})

// ============================================================
// 4. SUPER_ADMIN NAVIGATION
// ============================================================

test.describe('Super admin navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'super_admin')
    await setAuth(page, 'super_admin')
    await mockEmptyList(page, '/api/v1/admin/tenants')
  })

  test('logo navigates to /super-admin', async ({ page }) => {
    await page.goto('/super-admin')
    await page.click('[data-testid="navbar-logo"]')
    await expect(page).toHaveURL(/\/super-admin/)
  })

  test('shows Gestão Global only', async ({ page }) => {
    await page.goto('/super-admin')
    await expect(page.locator('[data-testid="nav-link-super-admin"]')).toBeVisible()
    // No admin management links
    await expect(page.locator('[data-testid="nav-link-courses"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="nav-link-classes"]')).toHaveCount(0)
  })
})

// ============================================================
// 5. RESPONSIVE — no horizontal overflow
// ============================================================

test.describe('Responsive — no horizontal overflow', () => {
  const viewports = [
    { width: 390, height: 844, name: 'iPhone 12 Pro' },
    { width: 430, height: 932, name: 'iPhone 14 Pro Max' },
    { width: 768, height: 1024, name: 'iPad' },
    { width: 1024, height: 768, name: 'iPad Landscape' },
    { width: 1440, height: 900, name: 'Desktop' },
  ]

  for (const vp of viewports) {
    test(`${vp.name} (${vp.width}x${vp.height}) — no horizontal overflow on Home`, async ({ page }) => {
      await mockTenantBranding(page)
      await page.route(`${API_BASE}/api/v1/courses`, (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
      )
      await page.setViewportSize({ width: vp.width, height: vp.height })
      await page.goto('/')
      await expect(page.locator('body')).toBeVisible()
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
      const clientWidth = await page.evaluate(() => document.documentElement.clientWidth)
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth)
    })

    test(`${vp.name} — no horizontal overflow on Login`, async ({ page }) => {
      await mockTenantBranding(page)
      await page.setViewportSize({ width: vp.width, height: vp.height })
      await page.goto('/login')
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
      const clientWidth = await page.evaluate(() => document.documentElement.clientWidth)
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth)
    })
  }

  test('mobile drawer opens and closes on small viewport', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/dashboard')
    // Hamburger should be visible
    await expect(page.locator('[data-testid="mobile-menu-toggle"]')).toBeVisible()
    // Open drawer
    await page.click('[data-testid="mobile-menu-toggle"]')
    await expect(page.locator('[data-testid="app-drawer-backdrop"]')).toBeVisible()
    // Click a nav link — drawer should close
    await page.click('[data-testid="nav-link-catalog"]')
    await expect(page.locator('[data-testid="app-drawer-backdrop"]')).toHaveCount(0)
  })
})

// ============================================================
// 6. ACCESSIBILITY
// ============================================================

test.describe('Accessibility', () => {
  test('hamburger has aria-expanded that changes on toggle', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/dashboard')
    const toggle = page.locator('[data-testid="mobile-menu-toggle"]')
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  })

  test('sidebar group button has aria-expanded that changes on click', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'admin')
    await setAuth(page, 'admin')
    await mockEmptyList(page, '/api/v1/courses')
    await mockEmptyList(page, '/api/v1/classes')
    await mockEmptyList(page, '/api/v1/students')
    await mockEmptyList(page, '/api/v1/enrollments')
    await mockEmptyList(page, '/api/v1/payments')
    await mockEmptyList(page, '/api/v1/certificates')
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/dashboard')
    const group = page.locator('[data-testid="nav-group-management"]')
    await expect(group).toHaveAttribute('aria-expanded', 'false')
    await group.click()
    await expect(group).toHaveAttribute('aria-expanded', 'true')
  })
})

// ============================================================
// 7. CONFIRM DIALOG BEHAVIOR
// ============================================================

test.describe('Confirm dialog behavior', () => {
  test('cancel does not perform action, confirm does', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'admin')
    await setAuth(page, 'admin')

    let deleteCalled = false
    // Courses list endpoint — match both with and without trailing slash
    await page.route('**/api/v1/courses**', (route) => {
      const url = route.request().url()
      const method = route.request().method()
      // Only handle DELETE for specific course URLs (e.g. /api/v1/courses/c1)
      if (method === 'DELETE') {
        deleteCalled = true
        route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      } else if (url.includes('/api/v1/courses/') && !url.includes('lessons') && !url.includes('progress') && !url.includes('learn')) {
        // List endpoint
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([
          { id: 'c1', code: 'NR-10', name: 'NR-10 Test', category: 'Seg', price: 100, is_active: true, carga_horaria: 8, modality: 'PRESENCIAL' }
        ]) })
      } else {
        route.continue()
      }
    })

    await page.goto('/courses')
    await expect(page.locator('text=NR-10 Test')).toBeVisible({ timeout: 10000 })

    // Click delete button
    await page.click('[data-testid="delete-course-btn"]')

    // Confirm dialog should appear
    await expect(page.locator('[data-testid="confirm-dialog-content"]')).toBeVisible()
    await expect(page.locator('[data-testid="confirm-ok"]')).toBeVisible()
    await expect(page.locator('[data-testid="confirm-cancel"]')).toBeVisible()

    // Cancel — should NOT delete
    await page.click('[data-testid="confirm-cancel"]')
    await expect(page.locator('[data-testid="confirm-dialog-content"]')).toHaveCount(0)
    expect(deleteCalled).toBe(false)

    // Reopen and confirm — should delete
    await page.click('[data-testid="delete-course-btn"]')
    await expect(page.locator('[data-testid="confirm-dialog-content"]')).toBeVisible()
    await page.click('[data-testid="confirm-ok"]')
    await page.waitForTimeout(500)
    expect(deleteCalled).toBe(true)
  })
})

// ============================================================
// 8. PASSWORD RECOVERY — token not exposed
// ============================================================

test.describe('Password recovery', () => {
  test.beforeEach(async ({ page }) => {
    await mockTenantBranding(page)
  })

  test('forgot password shows generic success, no token exposed', async ({ page }) => {
    // Backend accidentally returns reset_token — must NOT be displayed
    await page.route(`${API_BASE}/api/v1/auth/forgot-password`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ reset_token: 'SECRET-TOKEN-E2E' }),
      })
    )
    await page.goto('/recuperar-senha')
    await page.fill('[data-testid="forgot-email-input"]', 'test@example.com')
    await page.click('[data-testid="forgot-submit-btn"]')
    await expect(page.locator('[data-testid="forgot-success"]')).toBeVisible()
    // Token must NOT be visible
    await expect(page.locator('[data-testid="dev-reset-token"]')).toHaveCount(0)
    await expect(page.locator('text=SECRET-TOKEN-E2E')).toHaveCount(0)
  })

  test('reset password form works with token query param', async ({ page }) => {
    await page.route(`${API_BASE}/api/v1/auth/reset-password`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    )
    await page.goto('/redefinir-senha?token=QUERY-TOKEN-E2E')
    await expect(page.locator('[data-testid="reset-token-input"]')).toHaveValue('QUERY-TOKEN-E2E')
    await page.fill('[data-testid="reset-password-input"]', 'newpass123')
    await page.fill('[data-testid="reset-confirm-input"]', 'newpass123')
    await page.click('[data-testid="reset-submit-btn"]')
    await expect(page.locator('[data-testid="reset-success"]')).toBeVisible()
  })
})

// ============================================================
// 9. BACK/FORWARD/REFRESH
// ============================================================

test.describe('Back/Forward/Refresh', () => {
  test('dashboard survives refresh', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard/)
    await page.reload()
    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.locator('[data-testid="navbar-logo"]')).toBeVisible()
  })

  test('back and forward navigation works', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.route(`${API_BASE}/api/v1/courses`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    )
    await page.goto('/dashboard')
    await page.click('[data-testid="nav-link-catalog"]')
    await expect(page).toHaveURL(/\/cursos/)
    await page.goBack()
    await expect(page).toHaveURL(/\/dashboard/)
    await page.goForward()
    await expect(page).toHaveURL(/\/cursos/)
  })
})

// ============================================================
// 10. APPLICATION SHELL — persistent sidebar + topbar + full-width workspace
// ============================================================

test.describe('Application shell', () => {
  test('authenticated page renders sidebar, topbar and workspace markers', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.goto('/dashboard')
    await expect(page.locator('[data-testid="app-shell"]')).toBeVisible()
    await expect(page.locator('[data-testid="app-sidebar"]')).toBeVisible()
    await expect(page.locator('[data-testid="app-topbar"]')).toBeVisible()
    await expect(page.locator('[data-testid="app-workspace"]')).toBeVisible()
  })

  test('workspace is full-width — no root max-w-7xl centered container on dashboard', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/dashboard')
    const workspace = page.locator('[data-testid="app-workspace"]')
    await expect(workspace).toBeVisible()
    // The workspace must not be centered or width-capped at the root level
    const classes = await workspace.getAttribute('class')
    expect(classes).not.toContain('max-w-7xl')
    expect(classes).not.toContain('mx-auto')
    expect(classes).toContain('w-full')
  })

  test('sidebar persists across authenticated route changes', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'admin')
    await setAuth(page, 'admin')
    await mockEmptyList(page, '/api/v1/courses')
    await mockEmptyList(page, '/api/v1/classes')
    await mockEmptyList(page, '/api/v1/students')
    await mockEmptyList(page, '/api/v1/enrollments')
    await mockEmptyList(page, '/api/v1/payments')
    await mockEmptyList(page, '/api/v1/certificates')
    await page.goto('/dashboard')
    await expect(page.locator('[data-testid="app-sidebar"]')).toBeVisible()
    // Navigate to courses via sidebar group
    await page.click('[data-testid="nav-group-management"]')
    await page.click('[data-testid="nav-link-courses"]')
    await expect(page).toHaveURL(/\/courses/)
    // Sidebar is still there — shell is persistent
    await expect(page.locator('[data-testid="app-sidebar"]')).toBeVisible()
    await expect(page.locator('[data-testid="app-topbar"]')).toBeVisible()
  })

  test('public page does NOT render the app shell', async ({ page }) => {
    await mockTenantBranding(page)
    await page.route(`${API_BASE}/api/v1/courses`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    )
    await page.goto('/')
    await expect(page.locator('[data-testid="app-shell"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="app-sidebar"]')).toHaveCount(0)
    await expect(page.locator('[data-testid="app-topbar"]')).toHaveCount(0)
  })

  test('sidebar logo navigates to role home', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.goto('/dashboard')
    await page.click('[data-testid="navbar-logo"]')
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('sidebar logout clears auth and redirects to login', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.goto('/dashboard')
    await page.click('[data-testid="nav-logout"]')
    await expect(page).toHaveURL(/\/login/)
  })

  test('mobile drawer closes on Escape key', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'student')
    await setAuth(page, 'student')
    await mockEmptyList(page, '/api/v1/enrollments/me')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/dashboard')
    await page.click('[data-testid="mobile-menu-toggle"]')
    await expect(page.locator('[data-testid="app-drawer-backdrop"]')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('[data-testid="app-drawer-backdrop"]')).toHaveCount(0)
  })

  test('authenticated page has no horizontal overflow at desktop width', async ({ page }) => {
    await mockTenantBranding(page)
    await mockAuth(page, 'admin')
    await setAuth(page, 'admin')
    await mockEmptyList(page, '/api/v1/courses')
    await mockEmptyList(page, '/api/v1/classes')
    await mockEmptyList(page, '/api/v1/students')
    await mockEmptyList(page, '/api/v1/enrollments')
    await mockEmptyList(page, '/api/v1/payments')
    await mockEmptyList(page, '/api/v1/certificates')
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/dashboard')
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth)
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth)
  })
})
