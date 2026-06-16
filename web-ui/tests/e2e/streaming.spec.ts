import { test, expect } from '@playwright/test'

test.describe('SSE Streaming', () => {
  test.beforeEach(async ({ page }) => {
    // The Vue frontend calls /api/* but FastAPI has no /api prefix.
    // In dev mode Vite proxies /api/* → /*, but the Playwright webServer
    // runs FastAPI directly. We intercept /api/* routes:
    //   - /api/chat/stream → redirect to real /chat/stream (SSE streaming)
    //   - Other /api/* → mock with empty JSON (app handles failures gracefully)
    await page.route('**/api/**', async (route) => {
      const url = route.request().url()

      // Redirect SSE streaming requests to the real backend endpoint
      if (url.includes('/api/chat/stream')) {
        const newUrl = url.replace('/api/chat/stream', '/chat/stream')
        const response = await route.fetch({ url: newUrl })
        await route.fulfill({ response })
        return
      }

      // Mock other /api/* requests to avoid JSON parse errors
      if (url.includes('/api/datasets')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/skills')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/decisions')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      }
    })
  })

  test('chat stream emits SSE events and renders tokens', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await expect(input).toBeVisible()
    await input.fill('Hello, what is 2+2?')
    await page.locator('.send-btn').click()

    // User bubble should appear immediately (added to store before API call)
    await expect(page.locator('.user-bubble').first()).toBeVisible()

    // Wait for assistant response — streaming tokens arrive via SSE.
    // The actual CSS class is .ai-bubble (not .assistant-bubble).
    const aiBubble = page.locator('.ai-bubble').first()
    await expect(aiBubble).toBeVisible({ timeout: 30_000 })

    // Wait for actual content to accumulate beyond just the cursor blink
    await expect(async () => {
      const content = await aiBubble.textContent()
      expect(content).toBeTruthy()
      // Content should be more than just the cursor blink character
      expect(content!.replace(/\|/g, '').trim().length).toBeGreaterThan(0)
    }).toPass({ timeout: 30_000 })
  })

  test('/skill command syntax is accepted by input', async ({ page }) => {
    await page.goto('/')
    const input = page.locator('.chat-input')
    await input.fill('/skill data-cleaning')
    await expect(input).toHaveValue('/skill data-cleaning')
  })

  test('stream completes and input resets', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('Say hello world')
    await page.locator('.send-btn').click()

    // When streaming starts, the send button changes to a stop button (.stop-btn).
    // Wait for it to appear, then wait for it to disappear (streaming complete).
    await expect(page.locator('.stop-btn')).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.stop-btn')).toBeHidden({ timeout: 30_000 })

    // Input is cleared immediately in handleSend(), so it should be empty.
    await expect(input).toHaveValue('')

    // The send button should be back (though disabled since input is empty).
    await expect(page.locator('.send-btn')).toBeVisible()
  })
})
