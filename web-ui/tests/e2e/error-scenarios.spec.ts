import { test, expect } from '@playwright/test'

test.describe('Error Scenarios', () => {
  test.afterEach(async ({ page }) => {
    // Ignore dangling route.fetch errors from streams still in flight when test ends
    await page.unrouteAll({ behavior: 'ignoreErrors' })
  })

  test.beforeEach(async ({ page }) => {
    // API bridge: the Vue frontend calls /api/* but the Playwright webServer
    // runs FastAPI directly (no Vite proxy). Intercept /api/* routes:
    //   - /api/chat/stream → redirect to real /chat/stream (SSE streaming)
    //   - Other /api/* → mock with empty JSON (app handles failures gracefully)
    await page.route('**/api/**', async (route) => {
      const url = route.request().url()

      if (url.includes('/api/chat/stream')) {
        const newUrl = url.replace('/api/chat/stream', '/chat/stream')
        const response = await route.fetch({ url: newUrl })
        await route.fulfill({ response })
        return
      }

      if (url.includes('/api/datasets')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/skills')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/context')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ready: true, datasets: 0, decisions: 0 }),
        })
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      }
    })
  })

  test('empty message is rejected client-side', async ({ page }) => {
    await page.goto('/')
    const input = page.locator('.chat-input')
    await input.fill('')
    const sendBtn = page.locator('.send-btn')
    await expect(sendBtn).toBeDisabled()
  })

  test('invalid file format shows user-friendly feedback', async ({ page }) => {
    // Override upload to return a 422 error.
    // Registered after beforeEach, so it takes priority for matching requests.
    await page.route('**/api/upload', async (route) => {
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Unsupported file format: .txt' }),
      })
    })

    await page.goto('/')
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'invalid.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('this is not a valid data file'),
    })

    const errorEl = page.locator('.upload-error')
    await expect(errorEl).toBeVisible({ timeout: 10_000 })
    await expect(errorEl).toContainText('Unsupported file format')
  })

  test('rapid message sending does not crash the app', async ({ page }) => {
    await page.goto('/')
    const input = page.locator('.chat-input')
    const sendBtn = page.locator('.send-btn')

    for (let i = 0; i < 3; i++) {
      await input.fill('Quick message ' + i)
      await sendBtn.click()
      await page.waitForTimeout(500)
    }

    // App title remains visible — app did not crash
    await expect(page.locator('.app-title')).toBeVisible()
  })

  test('network error during streaming shows error state', async ({ page }) => {
    // Abort /api/chat/stream requests to simulate a network failure.
    // Registered after beforeEach's **/api/** bridge, so it takes priority.
    await page.route('**/api/chat/stream**', (route) => {
      route.abort('connectionreset')
    })

    await page.goto('/')
    const input = page.locator('.chat-input')
    await input.fill('Trigger a network error')
    await page.locator('.send-btn').click()

    // Error text is appended into the AI bubble as "[Error: ...]"
    const aiBubble = page.locator('.ai-bubble').first()
    await expect(aiBubble).toBeVisible({ timeout: 15_000 })
    await expect(aiBubble).toContainText('Error', { timeout: 15_000 })
  })

  test('LLM long response does not freeze UI', async ({ page }) => {
    await page.goto('/')
    const input = page.locator('.chat-input')
    await input.fill('Write a comprehensive analysis of data science best practices')
    await page.locator('.send-btn').click()

    // Streaming indicator (.cursor-blink) should appear during the long response
    await expect(page.locator('.cursor-blink')).toBeVisible({ timeout: 5_000 })

    // After 10 seconds of streaming, the app should still be responsive
    await page.waitForTimeout(10_000)
    await expect(page.locator('.app-title')).toBeVisible()
  })
})
