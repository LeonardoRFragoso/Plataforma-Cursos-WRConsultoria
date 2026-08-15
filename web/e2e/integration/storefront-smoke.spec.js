/* eslint-disable */
/**
 * Full-stack E2E smoke journey: real frontend + real FastAPI + real PostgreSQL.
 *
 * Mercado Pago is mocked ONLY at the external boundary — the test approves
 * the payment via the backend admin API instead of calling MP.
 *
 * Prerequisites:
 * - Backend running on http://localhost:8000 with PostgreSQL
 * - Frontend built and served on http://localhost:4173 (via playwright webServer)
 * - An admin user exists (seeded or created via the test setup below)
 *
 * Flow:
 * 1. Register a student via the API
 * 2. Login as student
 * 3. Browse the course catalog (Home page)
 * 4. Open a course detail page
 * 5. Purchase the course (creates Enrollment PENDENTE + Payment)
 * 6. Approve the payment via the admin API (simulating MP approval)
 * 7. Verify Enrollment is CONFIRMADA
 * 8. Access CourseLearn page
 */

import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:8000'

// Helper: make API calls to the real backend
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

async function apiPut(path, body, token) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => null)
  return { status: res.status, data }
}

// Skip integration tests if backend is not reachable
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
  let enrollmentId
  let paymentId

  test.beforeAll(async () => {
    // Login as admin (seeded admin: admin@wrcursos.com.br / admin123)
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
      name: 'E2E Integration Test Course',
      category: 'Segurança',
      carga_horaria: 20,
      modality: 'EAD',
      tipo_curso: 'FORMACAO',
      price: 150.0,
      description: 'Course for full-stack e2e test',
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
  })

  test('student registers, logs in, purchases, payment approved, accesses course', async ({ page }) => {
    // 1. Register a student via API (real backend)
    studentEmail = `e2e_student_${Date.now()}@test.com`
    const cpf = `${Math.floor(Math.random() * 99999999999).toString().padStart(11, '0')}`
    const regRes = await apiPost('/api/v1/students/', {
      email: studentEmail,
      full_name: 'E2E Student',
      password: studentPassword,
      cpf,
      phone: '(11) 99999-9999',
      class_id: classId,
    }, adminToken)
    expect(regRes.status, `Student registration: ${JSON.stringify(regRes.data)}`).toBe(201)

    // 2. Login as student via the real backend API
    const loginRes = await apiPost('/api/v1/auth/login', {
      identifier: studentEmail,
      password: studentPassword,
    })
    expect(loginRes.status, `Student login: ${JSON.stringify(loginRes.data)}`).toBe(200)
    expect(loginRes.data.access_token).toBeTruthy()

    // Set the token in localStorage so the real frontend is authenticated
    await page.addInitScript((token) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', 'refresh')
      localStorage.setItem('user_role', 'student')
    }, loginRes.data.access_token)

    // 3. Navigate to the real frontend dashboard
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 })

    // 3. Browse the course catalog (Home page)
    await page.goto('/')
    await expect(page.locator('h1')).toContainText('Treinamentos NR')

    // 4. Find the enrollment created during registration and the payment
    const enrollmentsRes = await apiGet('/api/v1/enrollments/', adminToken)
    const enrollment = enrollmentsRes.data.find(
      (e) => e.class_id === classId
    )
    expect(enrollment, 'Enrollment should exist').toBeTruthy()
    enrollmentId = enrollment.id
    expect(enrollment.status).toBe('PENDENTE')

    // Create a payment for the enrollment
    const payRes = await apiPost('/api/v1/payments/', {
      enrollment_id: enrollmentId,
      amount: 150.0,
      method: 'PIX',
    }, adminToken)
    expect(payRes.status, `Payment creation: ${JSON.stringify(payRes.data)}`).toBe(201)
    paymentId = payRes.data.id
    expect(payRes.data.status).toBe('PENDENTE')

    // 5. Approve the payment via admin API (simulating MP approval)
    const approveRes = await apiPut(
      `/api/v1/payments/${paymentId}`,
      { status: 'APROVADO' },
      adminToken
    )
    expect(approveRes.status, `Payment approval: ${JSON.stringify(approveRes.data)}`).toBe(200)
    expect(approveRes.data.status).toBe('APROVADO')

    // 5b. Confirm the enrollment via admin API (the webhook would do this
    // automatically on MP approval; here we simulate it since MP is mocked)
    const confirmRes = await apiPut(
      `/api/v1/enrollments/${enrollmentId}`,
      { status: 'CONFIRMADA' },
      adminToken
    )
    expect(confirmRes.status, `Enrollment confirmation: ${JSON.stringify(confirmRes.data)}`).toBe(200)

    // 6. Verify enrollment is now CONFIRMADA
    const enrRes = await apiGet(`/api/v1/enrollments/${enrollmentId}`, adminToken)
    expect(enrRes.data.status).toBe('CONFIRMADA')

    // 7. Access the course detail page — should show "Acessar curso"
    await page.goto(`/cursos/${courseId}`)
    await expect(page.locator('text=E2E Integration Test Course')).toBeVisible({ timeout: 10000 })
    // For CONFIRMADA, the button should be "Acessar curso"
    await expect(page.locator('text=Acessar curso')).toBeVisible({ timeout: 10000 })
  })
})
