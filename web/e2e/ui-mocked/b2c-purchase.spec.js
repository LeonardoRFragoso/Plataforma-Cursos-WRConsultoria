/* eslint-disable */
import { test, expect } from '@playwright/test'

// B2C purchase journey UI tests.
// Every API call is mocked: no real gateway credentials or money movement.

const API_BASE = 'http://localhost:8000'

const STUDENT_ME = {
  id: 'user-purchase-1',
  email: 'purchase@example.com',
  full_name: 'Purchase Student',
  role: 'student',
  cpf: '52998224725',
  is_active: true,
}

const PAID_COURSE = {
  id: 'course-paid-1',
  code: 'NR-35',
  name: 'NR-35 Trabalho em Altura',
  category: 'Segurança',
  price: 250.0,
  is_active: true,
  description: 'Curso NR-35',
  carga_horaria: 8,
  modality: 'EAD',
  type: 'FORMACAO',
  prerequisite: null,
}

const FREE_COURSE = {
  ...PAID_COURSE,
  id: 'course-free-1',
  code: 'INTRO-QSMS',
  name: 'Introdução ao QSMS',
  price: 0,
}

async function authenticateStudent(page) {
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'fake-purchase-token')
    localStorage.setItem('refresh_token', 'fake-purchase-refresh')
    localStorage.setItem('user_role', 'student')
  })

  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(STUDENT_ME),
    })
  )

  await page.route(`${API_BASE}/api/v1/tenants/branding*`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        name: 'WR Consultoria',
        logo_url: null,
        primary_color: '#0056b3',
        secondary_color: '#1a1a1a',
      }),
    })
  )
}

async function mockCourse(page, course) {
  await page.route(`${API_BASE}/api/v1/courses/${course.id}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(course),
    })
  )
}

test('B2C-FREE-001: curso gratuito confirma matrícula e nunca chama checkout', async ({ page }) => {
  await authenticateStudent(page)
  await mockCourse(page, FREE_COURSE)

  await page.route(`${API_BASE}/api/v1/enrollments/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  )

  let purchaseCalls = 0
  let checkoutCalls = 0

  await page.route(`${API_BASE}/api/v1/enrollments/purchase`, (route) => {
    purchaseCalls += 1
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        enrollment: {
          id: 'enrollment-free-1',
          student_id: 'student-1',
          class_id: 'class-free-1',
          price: 0,
          status: 'CONFIRMADA',
          source: 'INDIVIDUAL',
          enrollment_date: '2026-08-25T12:00:00',
          created_at: '2026-08-25T12:00:00',
          updated_at: '2026-08-25T12:00:00',
        },
        payment: null,
      }),
    })
  })

  await page.route(`${API_BASE}/api/v1/payments/*/checkout`, (route) => {
    checkoutCalls += 1
    route.fulfill({ status: 500, body: 'checkout must not be called for free course' })
  })

  await page.goto(`/cursos/${FREE_COURSE.id}`)
  await expect(page.getByRole('button', { name: 'Começar curso grátis' })).toBeVisible()
  await page.getByRole('button', { name: 'Começar curso grátis' }).click()

  await expect(page).toHaveURL(new RegExp(`/courses/${FREE_COURSE.id}/learn`))
  expect(purchaseCalls).toBe(1)
  expect(checkoutCalls).toBe(0)
})

test('B2C-PURCHASE-001: curso pago cria tentativa e redireciona ao checkout mock', async ({ page }) => {
  await authenticateStudent(page)
  await mockCourse(page, PAID_COURSE)

  await page.route(`${API_BASE}/api/v1/enrollments/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  )

  let purchaseCalls = 0
  let checkoutCalls = 0

  await page.route(`${API_BASE}/api/v1/enrollments/purchase`, (route) => {
    purchaseCalls += 1
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        enrollment: {
          id: 'enrollment-paid-1',
          student_id: 'student-1',
          class_id: 'class-paid-1',
          price: 250,
          status: 'PENDENTE',
          source: 'INDIVIDUAL',
          enrollment_date: '2026-08-25T12:00:00',
          created_at: '2026-08-25T12:00:00',
          updated_at: '2026-08-25T12:00:00',
        },
        payment: {
          id: 'payment-paid-1',
          enrollment_id: 'enrollment-paid-1',
          amount: 250,
          method: 'UNDEFINED',
          status: 'PENDENTE',
          provider: 'MERCADO_PAGO',
          created_at: '2026-08-25T12:00:00',
          updated_at: '2026-08-25T12:00:00',
        },
      }),
    })
  })

  await page.route(`${API_BASE}/api/v1/payments/payment-paid-1/checkout`, (route) => {
    checkoutCalls += 1
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        checkout_url: '/demo/payment/payment-paid-1',
        preference_id: 'mock-preference-1',
      }),
    })
  })

  await page.goto(`/cursos/${PAID_COURSE.id}`)
  await expect(page.getByRole('button', { name: 'Comprar agora' })).toBeVisible()
  await page.getByRole('button', { name: 'Comprar agora' }).click()

  await expect(page).toHaveURL(/\/demo\/payment\/payment-paid-1/)
  expect(purchaseCalls).toBe(1)
  expect(checkoutCalls).toBe(1)
})

test('PAY-ABANDON-001: matrícula pendente mostra retomada de pagamento', async ({ page }) => {
  await authenticateStudent(page)
  await mockCourse(page, PAID_COURSE)

  await page.route(`${API_BASE}/api/v1/enrollments/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'enrollment-pending-1',
          course_id: PAID_COURSE.id,
          course_name: PAID_COURSE.name,
          class_id: 'class-paid-1',
          status: 'PENDENTE',
          start_date: '2026-08-25',
          end_date: '2026-09-25',
          enrollment_date: '2026-08-25T12:00:00',
        },
      ]),
    })
  )

  await page.route(`${API_BASE}/api/v1/enrollments/purchase`, (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        enrollment: {
          id: 'enrollment-pending-1',
          student_id: 'student-1',
          class_id: 'class-paid-1',
          price: 250,
          status: 'PENDENTE',
          source: 'INDIVIDUAL',
          enrollment_date: '2026-08-25T12:00:00',
          created_at: '2026-08-25T12:00:00',
          updated_at: '2026-08-25T12:00:00',
        },
        payment: {
          id: 'payment-active-1',
          enrollment_id: 'enrollment-pending-1',
          amount: 250,
          method: 'UNDEFINED',
          status: 'PROCESSANDO',
          provider: 'MERCADO_PAGO',
          checkout_url: '/demo/payment/payment-active-1',
          provider_payment_id: 'mock-active-1',
          created_at: '2026-08-25T12:00:00',
          updated_at: '2026-08-25T12:00:00',
        },
      }),
    })
  )

  await page.route(`${API_BASE}/api/v1/payments/payment-active-1/checkout`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        checkout_url: '/demo/payment/payment-active-1',
        preference_id: 'mock-active-1',
        reused: true,
      }),
    })
  )

  await page.goto(`/cursos/${PAID_COURSE.id}`)
  await expect(page.getByRole('button', { name: 'Finalizar pagamento' })).toBeVisible()
  await page.getByRole('button', { name: 'Finalizar pagamento' }).click()

  await expect(page).toHaveURL(/\/demo\/payment\/payment-active-1/)
})
