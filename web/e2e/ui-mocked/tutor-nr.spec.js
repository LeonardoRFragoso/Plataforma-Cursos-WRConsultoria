/* eslint-disable */
import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:8001'

const mockAnswer = {
  answer: 'O EPI deve ser adequado ao risco e fornecido pelo empregador.',
  sources: [
    {
      label: 'NR-06 — Equipamento de Proteção Individual (EPI)',
      nr_code: 'NR-06',
      variant: '',
      heading: '',
    },
  ],
  suggestions: ['Quais EPIs são obrigatórios?'],
  confidence: 'HIGH',
  scope: ['NR-06'],
  knowledge_level: 'DEEP_KNOWLEDGE',
}

const mockSepAnswer = {
  answer: 'SEP é o Sistema Elétrico de Potência.',
  sources: [
    {
      label: 'NR-10 SEP — Sistema Elétrico de Potência',
      nr_code: 'NR-10',
      variant: 'SEP',
      heading: '',
    },
  ],
  suggestions: ['Quem pode trabalhar no SEP?'],
  confidence: 'HIGH',
  scope: ['NR-10'],
  knowledge_level: 'DEEP_KNOWLEDGE',
}

const mockComparisonAnswer = {
  answer: 'Esta pergunta envolve conhecimento de mais de um material (NR-33). Vou combinar as fontes relevantes.',
  sources: [
    { label: 'NR-33 — Trabalhador Autorizado em Espaços Confinados', nr_code: 'NR-33', variant: 'Trabalhador Autorizado', heading: '' },
    { label: 'NR-33 — Supervisor de Entrada em Espaços Confinados', nr_code: 'NR-33', variant: 'Supervisor', heading: '' },
  ],
  suggestions: ['Quais as responsabilidades do supervisor?'],
  confidence: 'HIGH',
  scope: ['NR-33'],
  knowledge_level: 'DEEP_KNOWLEDGE',
}

test.beforeEach(async ({ page }) => {
  // Mock tenant branding
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

  // Mock authenticated user
  await page.route(`${API_BASE}/api/v1/auth/me`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-1',
        full_name: 'Aluno Teste',
        role: 'student',
      }),
    })
  )

  // Simula token de auth no localStorage para o router guard
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'fake-token')
    localStorage.setItem('refresh_token', 'fake-refresh')
    localStorage.setItem('user_role', 'student')
  })
})

test('tutor responde pergunta sobre EPI com fonte NR-06', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/tutor/ask`, (route) => {
    const data = JSON.parse(route.request().postData() || '{}')
    if (data.question.toLowerCase().includes('epi')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAnswer),
      })
    }
    return route.fallback()
  })

  await page.goto('/dashboard')
  await page.click('[data-testid="nr-tutor-toggle"]')
  await expect(page.locator('[data-testid="tutor-input"]')).toBeVisible()

  await page.fill('[data-testid="tutor-input"]', 'Qual EPI devo utilizar?')
  await page.click('[data-testid="tutor-send-btn"]')

  await expect(page.locator('text=adequado ao risco')).toBeVisible()
  await expect(page.locator('text=NR-06')).toBeVisible()
})

test('tutor responde sobre SEP sem precisar citar NR-10', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/tutor/ask`, (route) => {
    const data = JSON.parse(route.request().postData() || '{}')
    if (data.question.toLowerCase().includes('sep')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSepAnswer),
      })
    }
    return route.fallback()
  })

  await page.goto('/dashboard')
  await page.click('[data-testid="nr-tutor-toggle"]')
  await page.fill('[data-testid="tutor-input"]', 'O que é SEP?')
  await page.click('[data-testid="tutor-send-btn"]')

  await expect(page.getByTestId('tutor-source-chip').filter({ hasText: 'Sistema Elétrico de Potência' })).toBeVisible()
  await expect(page.getByTestId('tutor-source-chip').filter({ hasText: 'NR-10 SEP' })).toBeVisible()
})

test('tutor permite follow-up mantendo contexto da conversa', async ({ page }) => {
  let callIndex = 0
  await page.route(`${API_BASE}/api/v1/tutor/ask`, (route) => {
    const data = JSON.parse(route.request().postData() || '{}')
    if (data.question.toLowerCase().includes('sep')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSepAnswer),
      })
    }
    if (data.question.toLowerCase().includes('trabalhar')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'Apenas trabalhadores autorizados e qualificados.',
          sources: [mockSepAnswer.sources[0]],
          suggestions: [],
          confidence: 'HIGH',
          scope: ['NR-10'],
          knowledge_level: 'DEEP_KNOWLEDGE',
        }),
      })
    }
    return route.fallback()
  })

  await page.goto('/dashboard')
  await page.click('[data-testid="nr-tutor-toggle"]')
  await page.fill('[data-testid="tutor-input"]', 'O que é SEP?')
  await page.click('[data-testid="tutor-send-btn"]')
  await expect(page.getByTestId('tutor-source-chip').filter({ hasText: 'Sistema Elétrico de Potência' })).toBeVisible()

  await page.fill('[data-testid="tutor-input"]', 'E quem pode trabalhar?')
  await page.click('[data-testid="tutor-send-btn"]')
  await expect(page.locator('text=autorizados e qualificados')).toBeVisible()
})

test('tutor responde sobre diferença entre trabalhador autorizado e supervisor', async ({ page }) => {
  await page.route(`${API_BASE}/api/v1/tutor/ask`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockComparisonAnswer),
    })
  )

  await page.goto('/dashboard')
  await page.click('[data-testid="nr-tutor-toggle"]')
  await page.fill(
    '[data-testid="tutor-input"]',
    'Qual a diferença entre trabalhador autorizado e supervisor em espaço confinado?'
  )
  await page.click('[data-testid="tutor-send-btn"]')

  await expect(page.locator('text=mais de um material')).toBeVisible()
  await expect(page.getByTestId('tutor-source-chip').filter({ hasText: 'Trabalhador Autorizado' })).toBeVisible()
  await expect(page.getByTestId('tutor-source-chip').filter({ hasText: 'Supervisor' })).toBeVisible()
})
