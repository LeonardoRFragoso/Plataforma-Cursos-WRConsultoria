/* eslint-disable */
import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:8000'

const BRANDING = {
  name: 'WR Consultoria',
  logo_url: null,
  logo_white_url: null,
  favicon_url: null,
  primary_color: '#047F37',
  secondary_color: '#17324D',
  accent_color: '#F59E0B',
}

const SUMMARY = {
  generated_at: '2026-08-27T00:00:00',
  course_status_counts: { COMPLIANCE_READY: 1 },
  enrollment_state_counts: { ENROLLED: 1 },
  signing_job_status_counts: {},
  reviews_expired: 0,
  reviews_due_30_days: 0,
  signer_profile_enabled: true,
  signer_certificate_expires_30_days: false,
  signer_certificate_expired: false,
  signer_certificate_not_after: '2027-08-27T00:00:00',
  enrollments_without_ledger_events: 0,
  approved_retention_policy_version: 1,
  retention_policy_ready: true,
}

const RETENTION_VERSIONS = [
  { id: 'v1', version: 1, status: 'APPROVED', created_at: '2026-01-01T00:00:00', certificate_retention_days: 365 },
  { id: 'v2', version: 2, status: 'DRAFT', created_at: '2026-08-27T00:00:00' },
]

const CLASSES = [
  { id: 'cls-1', description: 'Turma A', start_date: '2026-01-01', end_date: '2026-12-31' },
]

test.beforeEach(async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BRANDING) })
  )
  await page.route(`${API_BASE}/api/v1/auth/login`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'compliance-admin-token', refresh_token: 'refresh', token_type: 'bearer' }),
    })
  )
  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id: 'admin-1', email: 'admin@example.com', full_name: 'Administrador WR', role: 'admin', is_active: true }),
    })
  )
  await page.route(`${API_BASE}/api/v1/compliance/operations/summary`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SUMMARY) })
  )
  await page.route(`${API_BASE}/api/v1/compliance/operations/retention-policy/versions`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RETENTION_VERSIONS) })
  )
  await page.route(`${API_BASE}/api/v1/classes/`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CLASSES) })
  )
})

test('admin navega até Compliance NR e o dashboard carrega', async ({ page }) => {
  await page.goto('/login')
  await page.fill('[data-testid="login-identifier"]', 'admin@example.com')
  await page.fill('[data-testid="login-password"]', 'password123')
  await page.click('button[type="submit"]')

  await expect(page).toHaveURL(/\/dashboard/)
  // Expand the "Operações" nav group to reveal the Compliance NR link
  await page.getByTestId('nav-group-operations-group').click()
  await page.getByTestId('nav-link-compliance-operations').click()
  await expect(page).toHaveURL(/\/operations\/compliance/)

  await expect(page.getByText('Operação e auditoria')).toBeVisible()
  await expect(page.getByText('Revisões vencidas')).toBeVisible()
  await expect(page.getByText('Política versionada')).toBeVisible()
  await expect(page.getByText('APPROVED')).toBeVisible()
})
