import { test, expect } from '@playwright/test'

test.describe('WebSocket Connectivity', () => {
  test.beforeEach(async ({ page }) => {
    // Mock /api/** requests — FastAPI has no /api/ prefix routes.
    // Without mocking, these requests return index.html (SPA catch-all),
    // which breaks JSON parsing in the Vue app's onMounted fetches.
    await page.route('**/api/**', async (route) => {
      const url = route.request().url()
      if (url.includes('/api/datasets')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/skills')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/context')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{"ready":true,"datasets":0,"decisions":0}' })
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      }
    })
  })

  test('WebSocket connects and shows connected status', async ({ page }) => {
    await page.goto('/')

    // The Vue app's useWebSocket composable connects to /ws on mount.
    // When connected, App.vue shows <span class="status-dot connected">
    // with title="WebSocket connected".
    const wsDot = page.locator('.status-dot.connected')
    await expect(wsDot).toBeVisible({ timeout: 10_000 })
    await expect(wsDot).toHaveAttribute('title', 'WebSocket connected')
  })

  test('WebSocket reconnects after page reload', async ({ page }) => {
    await page.goto('/')

    const wsDot = page.locator('.status-dot.connected')
    await expect(wsDot).toBeVisible({ timeout: 10_000 })

    await page.reload()
    // After reload, the composable re-creates the WebSocket connection.
    // Use a longer timeout because the reconnect includes exponential backoff.
    await expect(page.locator('.status-dot.connected')).toBeVisible({ timeout: 15_000 })
  })

  test('WebSocket survives navigation within SPA', async ({ page }) => {
    await page.goto('/')

    const wsDot = page.locator('.status-dot.connected')
    await expect(wsDot).toBeVisible({ timeout: 10_000 })

    // Click into the chat input — this is client-side interaction only.
    await page.locator('.chat-input').click()
    await page.waitForTimeout(500)

    // WebSocket should still be connected after SPA interaction.
    await expect(page.locator('.status-dot.connected')).toBeVisible()
  })

  test('sidebar datasets section is visible', async ({ page }) => {
    await page.goto('/')

    // The first .section-title in the sidebar should be "Datasets".
    const sectionTitle = page.locator('.section-title').first()
    await expect(sectionTitle).toBeVisible({ timeout: 10_000 })
    await expect(sectionTitle).toHaveText('Datasets')
  })

  test('sidebar skills section is visible', async ({ page }) => {
    await page.goto('/')

    // The second .section-title should be "Skills".
    const sectionTitles = page.locator('.section-title')
    await expect(sectionTitles.nth(1)).toBeVisible({ timeout: 10_000 })
    await expect(sectionTitles.nth(1)).toHaveText('Skills')
  })
})
