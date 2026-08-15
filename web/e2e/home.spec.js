/* eslint-disable */
import { test, expect } from '@playwright/test'

test('página inicial carrega e exibe cursos', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toContainText('Treinamentos NR')
  await expect(page.locator('text=Cursos disponíveis')).toBeVisible()
})
