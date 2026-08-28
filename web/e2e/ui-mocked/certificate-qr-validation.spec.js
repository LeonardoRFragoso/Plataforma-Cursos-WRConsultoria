/* eslint-disable */
import { test, expect } from '@playwright/test'

// Certificate QR validation public journey — ui-mocked (no backend needed).
// Covers Phase 33: /validar-certificado?codigo=... auto-load, result, demo
// banner, course, student, timeline.

const API_BASE = 'http://localhost:8001'
const VALIDATION_CODE = 'DEMOABC1234567890'

const DEMO_VALIDATION_RESPONSE = {
  valid: true,
  status: 'ACTIVE',
  is_demo: true,
  certificate: {
    number: 'DEMO-CERT-DEMO001',
    validation_code: VALIDATION_CODE,
    version: 1,
    issued_at: '2026-08-15T10:00:00Z',
    expires_at: null,
    content_hash: 'a'.repeat(64),
  },
  student: { name: 'Aluno Demonstração WR' },
  course: {
    code: 'NR-01-F',
    name: 'Formação para Membros da CIPA',
    category: 'Segurança',
    workload_hours: 8,
    modality: 'EAD',
  },
  journey: {
    progress: {
      required_lessons_total: 3,
      required_lessons_completed: 3,
      completion_percent: 100.0,
    },
    steps: [
      { type: 'ENROLLED', label: 'Matrícula confirmada', occurred_at: '2026-08-10T10:00:00Z', order: 1 },
      { type: 'COURSE_STARTED', label: 'Curso iniciado', occurred_at: '2026-08-11T10:00:00Z', order: 2 },
      { type: 'LESSON_COMPLETED', label: '3 de 3 aulas obrigatórias concluídas', occurred_at: '2026-08-15T10:00:00Z', order: 3 },
      { type: 'COURSE_COMPLETED', label: 'Curso concluído', occurred_at: '2026-08-15T10:00:00Z', order: 4 },
      { type: 'CERTIFICATE_ISSUED', label: 'Certificado emitido', occurred_at: '2026-08-15T10:00:00Z', order: 5 },
    ],
    lessons: [
      { type: 'LESSON_COMPLETED', label: 'Aula concluída: Introdução', occurred_at: '2026-08-11T10:00:00Z', order: 0 },
    ],
  },
  certificate_number: 'DEMO-CERT-DEMO001',
  validation_code: VALIDATION_CODE,
  version: 1,
  student_name: 'Aluno Demonstração WR',
  course_name: 'Formação para Membros da CIPA',
  issued_at: '2026-08-15T10:00:00Z',
  expires_at: null,
  content_hash: 'a'.repeat(64),
}

test.beforeEach(async ({ page }) => {
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

test('CERT-QR-001: ?codigo= auto-valida e mostra banner demo + jornada', async ({ page }) => {
  let validateCalled = false
  await page.route(`${API_BASE}/api/v1/certificates/validate`, async (route) => {
    validateCalled = true
    const body = route.request().postDataJSON()
    expect(body.validation_code).toBe(VALIDATION_CODE)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(DEMO_VALIDATION_RESPONSE),
    })
  })

  await page.goto(`/validar-certificado?codigo=${VALIDATION_CODE}`)

  // Auto-validation happened
  await expect(page.getByTestId('validate-valid')).toBeVisible()
  expect(validateCalled).toBeTruthy()

  // Input is pre-filled
  await expect(page.getByTestId('validate-code-input')).toHaveValue(VALIDATION_CODE)

  // Demo banner is shown and clearly marked
  await expect(page.getByTestId('validate-demo-banner')).toBeVisible()
  await expect(page.getByText('Certificado de demonstração')).toBeVisible()
  await expect(page.getByText('Não possui validade oficial')).toBeVisible()

  // Student + course details
  await expect(page.getByText('Aluno Demonstração WR')).toBeVisible()
  await expect(page.getByText('Formação para Membros da CIPA')).toBeVisible()
  await expect(page.getByText('NR-01-F')).toBeVisible()
  await expect(page.getByText('8h')).toBeVisible()
  await expect(page.getByText('EAD')).toBeVisible()

  // Journey timeline
  await expect(page.getByTestId('validate-journey')).toBeVisible()
  await expect(page.getByText('Jornada até a emissão')).toBeVisible()
  await expect(page.getByText('3 de 3 aulas obrigatórias (100%)')).toBeVisible()
  await expect(page.getByTestId('journey-step-ENROLLED')).toBeVisible()
  await expect(page.getByTestId('journey-step-CERTIFICATE_ISSUED')).toBeVisible()

  // Integrity
  await expect(page.getByText('Integridade digital verificada')).toBeVisible()

  // Expand lesson details
  await page.getByTestId('validate-toggle-lessons').click()
  await expect(page.getByTestId('validate-lessons-list')).toBeVisible()
  await expect(page.getByText('Aula concluída: Introdução')).toBeVisible()
})

test('CERT-QR-002: ?code= retrocompatibilidade auto-valida', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/certificates/validate`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(DEMO_VALIDATION_RESPONSE),
    })
  )

  await page.goto(`/validar-certificado?code=${VALIDATION_CODE}`)
  await expect(page.getByTestId('validate-valid')).toBeVisible()
  await expect(page.getByTestId('validate-code-input')).toHaveValue(VALIDATION_CODE)
})

test('CERT-QR-003: NOT_FOUND mostra estado distinto', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/certificates/validate`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ valid: false, status: 'NOT_FOUND', is_demo: false }),
    })
  )

  await page.goto('/validar-certificado?codigo=NOPE-CODE')
  await expect(page.getByTestId('validate-invalid')).toBeVisible()
  await expect(page.getByText('Certificado não encontrado')).toBeVisible()
  // Demo banner must NOT appear for not-found
  await expect(page.getByTestId('validate-demo-banner')).toHaveCount(0)
})

test('CERT-QR-004: REVOKED mostra estado distinto com motivo', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/certificates/validate`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...DEMO_VALIDATION_RESPONSE,
        valid: false,
        status: 'REVOKED',
        is_demo: false,
        revocation_reason: 'Revogação administrativa',
      }),
    })
  )

  await page.goto('/validar-certificado?codigo=REV-CODE')
  await expect(page.getByTestId('validate-revoked')).toBeVisible()
  await expect(page.getByText('Certificado revogado')).toBeVisible()
  await expect(page.getByText('Revogação administrativa')).toBeVisible()
})
