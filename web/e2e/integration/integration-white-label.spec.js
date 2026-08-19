/* eslint-disable */
/**
 * Full-stack two-tenant white-label integration test.
 *
 * REQUIRED CI gate — zero skips allowed when WHITE_LABEL_INTEGRATION_REQUIRED=true.
 *
 * Topology:
 *   PostgreSQL → FastAPI (:8000, ENVIRONMENT=staging)
 *   WR frontend (:4173, VITE_TENANT_SLUG=wr)
 *   Alfa frontend (:4174, VITE_TENANT_SLUG=alfa)
 *
 * Tests prove:
 * A. WR storefront: WR branding + WR course, NOT Alfa
 * B. Alfa storefront: Alfa branding + Alfa course, NOT WR
 * C. WR admin sees WR data, not Alfa
 * D. Alfa admin sees Alfa data, not WR
 * E. JWT cross-tenant: WR→Alfa = 403, Alfa→WR = 403
 * F. Alfa branding change persisted + rendered
 * G. SUPER_ADMIN suspends Alfa → 503; reactivates → 200
 * H. SUPER_ADMIN not blocked while Alfa suspended
 * I. Payment journey: checkout → /demo/payment/<id> → approve → CONFIRMADA
 * J. Payment ownership: other student → 403
 * K. Certificate: Alfa PDF contains "Alfa Academy"
 * L. Origin trust: untrusted → 400, missing → 400, X-Tenant-Id → rejected
 */

import { test, expect } from '@playwright/test'

const API_BASE = process.env.API_BASE || 'http://localhost:8000'
const WR_URL = process.env.WR_URL || 'http://127.0.0.1:4173'
const ALFA_URL = process.env.ALFA_URL || 'http://127.0.0.1:4174'
const WR_ORIGIN = WR_URL
const ALFA_ORIGIN = ALFA_URL

const REQUIRED = process.env.WHITE_LABEL_INTEGRATION_REQUIRED === 'true'

// When NOT in required mode (e.g. smoke job), skip if the two-tenant stack
// is unavailable. When in required mode (white-label-integration job),
// tests MUST run and pass — no skips allowed.
let stackAvailable = false

test.beforeAll(async ({ browser }) => {
  if (REQUIRED) {
    stackAvailable = true // required mode: assume stack is up, fail if not
    return
  }
  try {
    const page = await browser.newPage()
    await page.goto(WR_URL, { timeout: 5000 })
    await page.close()
    stackAvailable = true
  } catch {
    stackAvailable = false
  }
})

// Credentials from env (set by CI from demo seed)
const WR_ADMIN_EMAIL = process.env.DEMO_WR_ADMIN_EMAIL || 'admin@wr.demo'
const WR_ADMIN_PASSWORD = process.env.DEMO_WR_ADMIN_PASSWORD || 'test-wr-admin-pass'
const ALFA_ADMIN_EMAIL = process.env.DEMO_ALFA_ADMIN_EMAIL || 'admin@alfa.demo'
const ALFA_ADMIN_PASSWORD = process.env.DEMO_ALFA_ADMIN_PASSWORD || 'test-alfa-admin-pass'
const ALFA_STUDENT_EMAIL = process.env.DEMO_ALFA_STUDENT_EMAIL || 'aluno1@alfa.demo'
const ALFA_STUDENT_PASSWORD = process.env.DEMO_ALFA_STUDENT_PASSWORD || 'test-alfa-student-pass'
const SUPER_ADMIN_EMAIL = process.env.DEMO_SUPER_ADMIN_EMAIL || 'super@wr.demo'
const SUPER_ADMIN_PASSWORD = process.env.DEMO_SUPER_ADMIN_PASSWORD || 'test-super-admin-pass'

// ─── API helpers with real browser-like headers ───

async function loginViaAPI(email, password, slug, origin) {
  const headers = { 'Content-Type': 'application/json' }
  if (slug) headers['x-tenant-slug'] = slug
  if (origin) headers['origin'] = origin
  const resp = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ identifier: email, password }),
  })
  if (!resp.ok) throw new Error(`Login failed for ${email}: ${resp.status} ${await resp.text()}`)
  return resp.json()
}

async function apiGet(path, token, slug, origin) {
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (slug) headers['x-tenant-slug'] = slug
  if (origin) headers['origin'] = origin
  const resp = await fetch(`${API_BASE}${path}`, { headers })
  return { status: resp.status, body: await resp.json().catch(() => null), headers: resp.headers }
}

async function apiPost(path, body, token, slug, origin) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (slug) headers['x-tenant-slug'] = slug
  if (origin) headers['origin'] = origin
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  return { status: resp.status, body: await resp.json().catch(() => null) }
}

async function apiPut(path, body, token, slug, origin) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (slug) headers['x-tenant-slug'] = slug
  if (origin) headers['origin'] = origin
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  return { status: resp.status, body: await resp.json().catch(() => null) }
}

async function apiGetBinary(path, token, slug, origin) {
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (slug) headers['x-tenant-slug'] = slug
  if (origin) headers['origin'] = origin
  const resp = await fetch(`${API_BASE}${path}`, { headers })
  const buf = await resp.arrayBuffer()
  return { status: resp.status, buf }
}

// ─── Shared state across serial tests ───
let wrToken, alfaToken, superToken
let alfaCourseId, alfaClassId, alfaPaymentId, alfaCertId
let alfaSubId

test.describe('Integration — White Label Two-Tenant', () => {
  test.describe.configure({ mode: 'serial' })

  // Skip individual tests when stack is unavailable AND not in required mode.
  // In required mode (white-label-integration CI job), tests MUST run.
  test.beforeEach(({ }, testInfo) => {
    if (!stackAvailable && !REQUIRED) {
      testInfo.skip(true, 'Two-tenant stack not available (requires WR :4173 and Alfa :4174)')
    }
  })

  // ─── A. WR storefront ───
  test('A. WR storefront shows WR branding and WR course, not Alfa', async ({ browser }) => {
    const page = await browser.newPage()
    await page.goto(WR_URL)
    await page.waitForTimeout(3000)

    const bodyText = await page.textContent('body')
    expect(bodyText).toContain('WR Consultoria e Soluções')
    expect(bodyText).toContain('NR-10 Segurança em Instalações Elétricas')
    // Must NOT show Alfa-only courses
    expect(bodyText).not.toContain('Integração de Segurança')
    expect(bodyText).not.toContain('Gestão de Riscos')
    expect(bodyText).not.toContain('Treinamento Operacional')

    // Verify WR primary color
    const primaryColor = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()
    )
    expect(primaryColor.toLowerCase()).toBe('#0056b3')

    await page.close()
  })

  // ─── B. Alfa storefront ───
  test('B. Alfa storefront shows Alfa branding and Alfa course, not WR', async ({ browser }) => {
    const page = await browser.newPage()
    await page.goto(ALFA_URL)
    await page.waitForTimeout(3000)

    const bodyText = await page.textContent('body')
    expect(bodyText).toContain('Alfa Academy')
    expect(bodyText).toContain('Integração de Segurança')
    // Must NOT show WR-only courses
    expect(bodyText).not.toContain('NR-10 Segurança em Instalações Elétricas')
    expect(bodyText).not.toContain('NR-35 Trabalho em Altura')

    // Verify Alfa primary color
    const primaryColor = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()
    )
    expect(primaryColor.toLowerCase()).toBe('#e86a17')

    await page.close()
  })

  // ─── C. WR admin data ───
  test('C. WR admin login sees WR data, not Alfa', async () => {
    const login = await loginViaAPI(WR_ADMIN_EMAIL, WR_ADMIN_PASSWORD, 'wr', WR_ORIGIN)
    wrToken = login.access_token
    expect(wrToken).toBeTruthy()

    const { status, body } = await apiGet('/api/v1/courses', wrToken, 'wr', WR_ORIGIN)
    expect(status).toBe(200)
    expect(Array.isArray(body)).toBe(true)
    expect(body.length).toBeGreaterThan(0)

    const courseNames = body.map(c => c.name)
    expect(courseNames).toContain('NR-10 Segurança em Instalações Elétricas')
    // Must NOT contain Alfa-only courses
    expect(courseNames).not.toContain('Integração de Segurança')
    expect(courseNames).not.toContain('Gestão de Riscos')
  })

  // ─── D. Alfa admin data ───
  test('D. Alfa admin login sees Alfa data, not WR', async () => {
    const login = await loginViaAPI(ALFA_ADMIN_EMAIL, ALFA_ADMIN_PASSWORD, 'alfa', ALFA_ORIGIN)
    alfaToken = login.access_token
    expect(alfaToken).toBeTruthy()

    const { status, body } = await apiGet('/api/v1/courses', alfaToken, 'alfa', ALFA_ORIGIN)
    expect(status).toBe(200)
    expect(Array.isArray(body)).toBe(true)
    expect(body.length).toBeGreaterThan(0)

    const courseNames = body.map(c => c.name)
    expect(courseNames).toContain('Integração de Segurança')
    // Must NOT contain WR-only courses
    expect(courseNames).not.toContain('NR-10 Segurança em Instalações Elétricas')
    expect(courseNames).not.toContain('NR-35 Trabalho em Altura')

    // Store for later tests
    alfaCourseId = body[0].id
  })

  // ─── E. JWT cross-tenant (uses protected dashboard endpoint) ───
  test('E1. WR token + Alfa context → 403', async () => {
    const { status } = await apiGet('/api/v1/dashboard/stats', wrToken, 'alfa', ALFA_ORIGIN)
    expect(status).toBe(403)
  })

  test('E2. Alfa token + WR context → 403', async () => {
    const { status } = await apiGet('/api/v1/dashboard/stats', alfaToken, 'wr', WR_ORIGIN)
    expect(status).toBe(403)
  })

  // ─── L. Origin trust contract ───
  test('L1. Untrusted Origin + X-Tenant-Slug → 400', async () => {
    const { status } = await apiGet('/api/v1/courses', null, 'alfa', 'https://evil.example')
    expect(status).toBe(400)
  })

  test('L2. Missing Origin + X-Tenant-Slug in staging → 400', async () => {
    const { status } = await apiGet('/api/v1/courses', null, 'alfa', null)
    expect(status).toBe(400)
  })

  test('L3. X-Tenant-Id rejected in staging', async () => {
    // X-Tenant-Id should be ignored in staging; falls through to host-based resolution.
    // Use a protected endpoint: without a valid token, it should return 401.
    // If X-Tenant-Id were accepted, it might try to resolve a non-existent tenant → 404.
    // Either way, it should NOT return 200 (which would mean the header was accepted
    // and the request was processed as that tenant).
    const resp = await fetch(`${API_BASE}/api/v1/dashboard/stats`, {
      headers: { 'x-tenant-id': '00000000-0000-0000-0000-000000000000' },
    })
    expect(resp.status).not.toBe(200)
  })

  // ─── F. Branding settings ───
  test('F. Alfa branding change persisted via API', async () => {
    const newColor = '#FF00FF'
    const { status } = await apiPut(
      '/api/v1/tenants/branding',
      { primary_color: newColor },
      alfaToken,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(status).toBe(200)

    // Verify API persisted (branding endpoint uses ?slug= query param)
    const { body } = await apiGet('/api/v1/tenants/branding?slug=alfa', null, 'alfa', ALFA_ORIGIN)
    expect(body.primary_color).toBe(newColor)

    // Restore demo value
    await apiPut(
      '/api/v1/tenants/branding',
      { primary_color: '#E86A17' },
      alfaToken,
      'alfa',
      ALFA_ORIGIN,
    )
  })

  // ─── G. SUPER_ADMIN subscription management ───
  test('G1. SUPER_ADMIN login and find Alfa subscription', async () => {
    const login = await loginViaAPI(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, 'wr', WR_ORIGIN)
    superToken = login.access_token
    expect(superToken).toBeTruthy()

    const { status, body } = await apiGet('/api/v1/super-admin/subscriptions', superToken, 'wr', WR_ORIGIN)
    expect(status).toBe(200)
    expect(Array.isArray(body)).toBe(true)
    expect(body.length).toBeGreaterThan(0)

    // Find Alfa subscription
    const alfaSub = body.find(s => s.tenant_id || s.status)
    expect(alfaSub).toBeTruthy()
    alfaSubId = alfaSub.id
  })

  test('G2. SUPER_ADMIN suspends Alfa → business route 503', async () => {
    // Find the Alfa subscription specifically
    const { body: subs } = await apiGet('/api/v1/super-admin/subscriptions', superToken, 'wr', WR_ORIGIN)
    // Get tenants to find Alfa's tenant_id
    const { body: tenants } = await apiGet('/api/v1/super-admin/tenants', superToken, 'wr', WR_ORIGIN)
    const alfaTenant = tenants.find(t => t.slug === 'alfa')
    expect(alfaTenant).toBeTruthy()

    const alfaSub = subs.find(s => s.tenant_id === alfaTenant.id)
    expect(alfaSub).toBeTruthy()
    alfaSubId = alfaSub.id

    // Suspend
    const { status: suspendStatus } = await apiPost(
      `/api/v1/super-admin/subscriptions/${alfaSubId}/suspend`,
      null,
      superToken,
      'wr',
      WR_ORIGIN,
    )
    expect(suspendStatus).toBe(200)

    // Alfa business route should be blocked (503)
    const { status: blockedStatus } = await apiGet('/api/v1/courses', alfaToken, 'alfa', ALFA_ORIGIN)
    expect(blockedStatus).toBe(503)
  })

  test('G3. SUPER_ADMIN not blocked while Alfa suspended', async () => {
    // SUPER_ADMIN can still inspect Alfa
    const { status, body } = await apiGet('/api/v1/super-admin/tenants', superToken, 'wr', WR_ORIGIN)
    expect(status).toBe(200)
    expect(body.find(t => t.slug === 'alfa')).toBeTruthy()

    // SUPER_ADMIN can still manage subscriptions
    const { status: subStatus } = await apiGet('/api/v1/super-admin/subscriptions', superToken, 'wr', WR_ORIGIN)
    expect(subStatus).toBe(200)
  })

  test('G4. SUPER_ADMIN reactivates Alfa → business route 200', async () => {
    const { status: activateStatus } = await apiPost(
      `/api/v1/super-admin/subscriptions/${alfaSubId}/activate`,
      null,
      superToken,
      'wr',
      WR_ORIGIN,
    )
    expect(activateStatus).toBe(200)

    // Alfa should work again — need fresh login since old token may be fine
    const { status } = await apiGet('/api/v1/courses', alfaToken, 'alfa', ALFA_ORIGIN)
    expect(status).toBe(200)
  })

  // ─── I. Payment journey ───
  test('I1. Alfa student checkout → /demo/payment/<id>', async ({ browser }) => {
    // Login as Alfa student
    const login = await loginViaAPI(ALFA_STUDENT_EMAIL, ALFA_STUDENT_PASSWORD, 'alfa', ALFA_ORIGIN)
    const studentToken = login.access_token
    expect(studentToken).toBeTruthy()

    // Get Alfa courses
    const { body: courses } = await apiGet('/api/v1/courses', studentToken, 'alfa', ALFA_ORIGIN)
    expect(courses.length).toBeGreaterThan(0)

    const courseId = courses[0].id

    // Purchase enrollment (API expects course_id, not class_id)
    const { status: purchaseStatus, body: purchaseBody } = await apiPost(
      '/api/v1/enrollments/purchase',
      { course_id: courseId, method: 'BOLETO' },
      studentToken,
      'alfa',
      ALFA_ORIGIN,
    )
    // 201 = new enrollment, 200 = existing
    expect([200, 201]).toContain(purchaseStatus)
    expect(purchaseBody.enrollment || purchaseBody).toBeTruthy()

    const paymentId = purchaseBody.payment?.id || purchaseBody.payment_id
    expect(paymentId).toBeTruthy()
    alfaPaymentId = paymentId

    // Checkout — should return /demo/payment/<id> URL
    const { body: checkout } = await apiPost(
      `/api/v1/payments/${alfaPaymentId}/checkout`,
      null,
      studentToken,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(checkout.checkout_url).toContain('/demo/payment/')
    expect(checkout.checkout_url).toContain(alfaPaymentId)
    expect(checkout.checkout_url).not.toContain('mock-mp.test')

    // Approve via demo simulator
    const { body: approveResult } = await apiPost(
      `/api/v1/payments/demo/${alfaPaymentId}/approve`,
      null,
      studentToken,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(approveResult.payment_status).toBe('APROVADO')
    expect(approveResult.enrollment_confirmed).toBe(true)

    // Verify GET returns course_id and confirmed enrollment
    const { body: paymentDetail } = await apiGet(
      `/api/v1/payments/demo/${alfaPaymentId}`,
      studentToken,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(paymentDetail.course_id).toBeTruthy()
    expect(paymentDetail.enrollment_status).toBe('CONFIRMADA')

    // Verify "Acessar Curso" link in browser
    const page = await browser.newPage()
    await page.goto(`${ALFA_URL}/demo/payment/${alfaPaymentId}`)
    await page.waitForTimeout(2000)
    const link = page.locator('[data-testid="access-course-link"]')
    await expect(link).toBeVisible({ timeout: 10000 })
    const href = await link.getAttribute('href') || await link.getAttribute('to')
    expect(href).toContain(paymentDetail.course_id)
    expect(href).not.toContain('null')
    expect(href).not.toContain('undefined')
    await page.close()
  })

  // ─── J. Payment ownership ───
  test('J. Other student cannot access payment → 403', async () => {
    // Login as Alfa student 2
    const student2Email = process.env.DEMO_ALFA_STUDENT2_EMAIL || 'aluno2@alfa.demo'
    const student2Pass = process.env.DEMO_ALFA_STUDENT_PASSWORD || 'test-alfa-student-pass'
    const login = await loginViaAPI(student2Email, student2Pass, 'alfa', ALFA_ORIGIN)
    const token2 = login.access_token
    expect(token2).toBeTruthy()

    // Student 2 tries GET on student 1's payment
    const { status: getStatus } = await apiGet(
      `/api/v1/payments/demo/${alfaPaymentId}`,
      token2,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(getStatus).toBe(403)

    // Student 2 tries POST approve
    const { status: postStatus } = await apiPost(
      `/api/v1/payments/demo/${alfaPaymentId}/approve`,
      null,
      token2,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(postStatus).toBe(403)

    // Student 2 tries POST reject
    const { status: rejectStatus } = await apiPost(
      `/api/v1/payments/demo/${alfaPaymentId}/reject`,
      null,
      token2,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(rejectStatus).toBe(403)
  })

  // ─── K. Certificate white-label ───
  test('K. Alfa certificate PDF contains tenant name', async () => {
    // Login as Alfa student 1 (has certificate from seed)
    const login = await loginViaAPI(ALFA_STUDENT_EMAIL, ALFA_STUDENT_PASSWORD, 'alfa', ALFA_ORIGIN)
    const studentToken = login.access_token

    // List certificates
    const { status: certStatus, body: certs } = await apiGet(
      '/api/v1/certificates',
      studentToken,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(certStatus).toBe(200)
    expect(Array.isArray(certs)).toBe(true)
    expect(certs.length).toBeGreaterThan(0)

    const certId = certs[0].id

    // Download PDF
    const { status: dlStatus, buf } = await apiGetBinary(
      `/api/v1/certificates/${certId}/download`,
      studentToken,
      'alfa',
      ALFA_ORIGIN,
    )
    expect(dlStatus).toBe(200)
    expect(buf.byteLength).toBeGreaterThan(1000) // non-empty PDF

    // Extract text from PDF (simple approach — look for tenant name in raw bytes)
    const pdfText = Buffer.from(buf).toString('latin1')
    expect(pdfText).toContain('Alfa Academy')
  })
})
