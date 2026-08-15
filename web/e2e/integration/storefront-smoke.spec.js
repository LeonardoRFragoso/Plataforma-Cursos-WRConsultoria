/* eslint-disable */
/**
 * Full-stack E2E smoke journey: real frontend + real FastAPI + real PostgreSQL.
 *
 * Mercado Pago is mocked ONLY at the external API boundary via
 * MERCADO_PAGO_MOCK_MODE=true on the backend. The webhook flow is real.
 *
 * Prerequisites:
 * - Backend running on http://localhost:8000 with PostgreSQL
 * - MERCADO_PAGO_MOCK_MODE=true on the backend
 * - Frontend served on baseURL (http://localhost:5173 for docker, 4173 for local preview)
 * - An admin user exists (admin@wrcursos.com.br / admin123)
 *
 * Flow:
 * 1. Create course + class via admin API (real backend)
 * 2. Register a student via admin API (real backend)
 * 3. Login as student via the real backend API
 * 4. Open CourseDetail in the real frontend
 * 5. Click "Comprar" → POST /enrollments/purchase (real)
 * 6. Verify Enrollment PENDENTE + Payment PENDENTE (real)
 * 7. POST /payments/{id}/checkout (real) → mock MP preference
 * 8. POST /payments/webhook/mercado-pago (real webhook) → mock MP verification
 * 9. Verify Payment APROVADO + Enrollment CONFIRMADA (real)
 * 10. Open CourseDetail → "Acessar curso" visible
 * 11. Access CourseLearn page
 */

import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:8000'

/**
 * Generates a valid CPF from a 9-digit seed.
 * Computes the 2 check digits using the CPF algorithm.
 * Deterministic — same seed always produces the same valid CPF.
 */
function generateValidCpf(seed) {
  const base = String(seed).padStart(9, '0').slice(-9).split('').map(Number)
  // First check digit
  let sum = 0
  for (let i = 0; i < 9; i++) sum += base[i] * (10 - i)
  let d1 = 11 - (sum % 11)
  if (d1 >= 10) d1 = 0
  // Second check digit
  sum = 0
  for (let i = 0; i < 9; i++) sum += base[i] * (11 - i)
  sum += d1 * 2
  let d2 = 11 - (sum % 11)
  if (d2 >= 10) d2 = 0
  return base.join('') + d1 + d2
}

// Deterministic valid CPF from timestamp seed (unique per run, always valid)
const STUDENT_CPF = generateValidCpf(Date.now() % 1000000000)

async function apiPost(path, body, token) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => null)
  return { status: res.status, data }
}

async function apiGet(path, token) {
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { headers })
  const data = await res.json().catch(() => null)
  return { status: res.status, data }
}

test.describe('full-stack storefront smoke', () => {
  test.skip(async () => {
    try {
      const res = await fetch(`${API_BASE}/docs`, { signal: AbortSignal.timeout(3000) })
      return !res.ok
    } catch {
      return true // skip if backend not available
    }
  })

  let adminToken
  let studentEmail
  let studentPassword = 'student123'
  let courseId
  let classId
  let studentToken
  let enrollmentId
  let paymentId

  test.beforeAll(async () => {
    // Login as admin (seeded: admin@wrcursos.com.br / admin123)
    const loginRes = await apiPost('/api/v1/auth/login', {
      identifier: 'admin@wrcursos.com.br',
      password: 'admin123',
    })
    if (loginRes.status !== 200) {
      throw new Error(`Admin login failed: ${loginRes.status} ${JSON.stringify(loginRes.data)}`)
    }
    adminToken = loginRes.data.access_token

    // Create a course for the test
    const courseRes = await apiPost('/api/v1/courses/', {
      code: `E2E-${Date.now().toString(36).toUpperCase()}`,
      name: 'E2E Purchase Flow Course',
      category: 'Segurança',
      carga_horaria: 20,
      modality: 'EAD',
      tipo_curso: 'FORMACAO',
      price: 150.0,
      description: 'Course for full-stack purchase e2e test',
    }, adminToken)
    expect(courseRes.status, `Course creation: ${JSON.stringify(courseRes.data)}`).toBe(201)
    courseId = courseRes.data.id

    // Create a class
    const me = await apiGet('/api/v1/auth/me', adminToken)
    const adminId = me.data.id
    const today = new Date()
    const start = new Date(today.getTime() + 86400000).toISOString().split('T')[0]
    const end = new Date(today.getTime() + 30 * 86400000).toISOString().split('T')[0]
    const classRes = await apiPost('/api/v1/classes/', {
      course_id: courseId,
      responsible_admin_id: adminId,
      start_date: start,
      end_date: end,
      max_students: 25,
      ead_link: 'https://ead.test/e2e',
      status: 'ABERTA',
      description: 'E2E test class',
    }, adminToken)
    expect(classRes.status, `Class creation: ${JSON.stringify(classRes.data)}`).toBe(201)
    classId = classRes.data.id

    // Register a student via admin API (real backend)
    studentEmail = `e2e_purchase_${Date.now()}@test.com`
    const regRes = await apiPost('/api/v1/students/', {
      email: studentEmail,
      full_name: 'E2E Purchase Student',
      password: studentPassword,
      cpf: STUDENT_CPF,
      phone: '(11) 99999-9999',
      class_id: classId,
    }, adminToken)
    expect(regRes.status, `Student registration: ${JSON.stringify(regRes.data)}`).toBe(201)

    // Login as student via the real backend API
    const studentLogin = await apiPost('/api/v1/auth/login', {
      identifier: studentEmail,
      password: studentPassword,
    })
    expect(studentLogin.status, `Student login: ${JSON.stringify(studentLogin.data)}`).toBe(200)
    studentToken = studentLogin.data.access_token
  })

  test('student purchases course via real backend, webhook approves, course accessible', async ({ page }) => {
    // Set the token in localStorage so the real frontend is authenticated
    await page.addInitScript((token) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', 'refresh')
      localStorage.setItem('user_role', 'student')
    }, studentToken)

    // 4. Open CourseDetail in the real frontend
    await page.goto(`/cursos/${courseId}`)
    await expect(page.locator('text=E2E Purchase Flow Course')).toBeVisible({ timeout: 10000 })

    // 5. Click "Comprar" → triggers POST /enrollments/purchase (real)
    //    The frontend also calls createCheckout which redirects to MP mock URL.
    //    We intercept the mock MP URL to prevent navigation error.
    await page.route('http://mock-mp.test/**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: '<html><body><h1>Mock MP Checkout</h1></body></html>',
      })
    )

    // Click the purchase button (text varies: "Comprar agora", "Finalizar pagamento", etc.)
    const purchaseButton = page.locator('button:has-text("Comprar agora"), button:has-text("Finalizar pagamento"), button:has-text("Comprar novamente")')
    await purchaseButton.first().click()

    // Wait for the purchase + checkout to complete (backend calls)
    // The page will try to navigate to mock-mp.test — intercepted above
    await page.waitForTimeout(3000)

    // 6. Verify Enrollment PENDENTE + Payment exists via API
    //    (Payment may be PENDENTE or PROCESSANDO depending on whether
    //    the frontend's checkout call has already completed)
    const enrollmentsRes = await apiGet('/api/v1/enrollments/', adminToken)
    const enrollment = enrollmentsRes.data.find(
      (e) => e.class_id === classId
    )
    expect(enrollment, 'Enrollment should exist after purchase').toBeTruthy()
    enrollmentId = enrollment.id
    expect(enrollment.status).toBe('PENDENTE')

    // Find the payment for this enrollment (list all and filter)
    const paymentsRes = await apiGet('/api/v1/payments/', adminToken)
    const payment = paymentsRes.data.find((p) => p.enrollment_id === enrollmentId)
    expect(payment, 'Payment should exist after purchase').toBeTruthy()
    paymentId = payment.id
    // Payment should be PENDENTE (just created) or PROCESSANDO (checkout ran)
    expect(['PENDENTE', 'PROCESSANDO']).toContain(payment.status)

    // 7. Call checkout via API to ensure mercado_pago_id is set on the payment
    //    (the frontend may have already done this)
    const checkoutRes = await apiPost(
      `/api/v1/payments/${paymentId}/checkout`,
      {},
      studentToken
    )
    expect(checkoutRes.status, `Checkout: ${JSON.stringify(checkoutRes.data)}`).toBe(200)
    expect(checkoutRes.data.preference_id).toBeTruthy()

    // 8. Call the real webhook to simulate MP approval
    //    The webhook calls get_payment_info (mocked MP) → returns approved
    //    The webhook then sets Payment APROVADO + Enrollment CONFIRMADA
    const webhookRes = await apiPost('/api/v1/payments/webhook/mercado-pago', {
      id: `mock-mp-payment-${enrollmentId}`,
      status: 'approved',
      external_reference: enrollmentId,
    })
    expect(webhookRes.status, `Webhook: ${JSON.stringify(webhookRes.data)}`).toBe(200)
    expect(webhookRes.data.status).toBe('ok')

    // 9. Verify Payment APROVADO + Enrollment CONFIRMADA via API
    const payAfter = await apiGet(`/api/v1/payments/${paymentId}`, adminToken)
    expect(payAfter.data.status).toBe('APROVADO')

    const enrAfter = await apiGet(`/api/v1/enrollments/${enrollmentId}`, adminToken)
    expect(enrAfter.data.status).toBe('CONFIRMADA')

    // 10. Open CourseDetail → "Acessar curso" should be visible
    await page.goto(`/cursos/${courseId}`)
    await expect(page.locator('text=E2E Purchase Flow Course')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=Acessar curso')).toBeVisible({ timeout: 10000 })

    // 11. Access CourseLearn page
    await page.click('a:has-text("Acessar curso")')
    await expect(page).toHaveURL(/\/courses\/.*\/learn/, { timeout: 10000 })
  })
})
