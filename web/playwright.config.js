import { defineConfig, devices } from '@playwright/test'

/**
 * Two e2e suites:
 * - ui-mocked: browser/UI integration with mocked API (no backend needed)
 * - integration: full-stack with real FastAPI + PostgreSQL backend
 *   (requires backend running on localhost:8000)
 *
 * baseURL is configurable via PLAYWRIGHT_BASE_URL env var:
 * - local preview (ui-mocked): http://localhost:4173 (vite preview)
 * - docker CI (integration):   http://localhost:5173 (vite dev in docker)
 */
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:4173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'ui-mocked',
      testDir: './e2e/ui-mocked',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'integration',
      testDir: './e2e/integration',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined // external server (docker); don't start our own
    : {
        command: 'npm run build && npm run preview -- --port 4173',
        url: 'http://localhost:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 120000,
      },
})
