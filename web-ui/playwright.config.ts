import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['html'], ['list']],
  use: {
    baseURL: 'http://127.0.0.1:9000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'python -m uvicorn serve:app --host 127.0.0.1 --port 9000',
    url: 'http://127.0.0.1:9000/health',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: {
      DATAMIND_PROVIDER: 'deepseek',
      DATAMIND_MODEL: 'deepseek-v4-flash',
      DATAMIND_API_KEY: process.env.DATAMIND_API_KEY,
      DATAMIND_API_BASE: 'https://api.deepseek.com',
      DATAMIND_LOG_LEVEL: 'INFO',
    },
    cwd: '.',
  },
})
