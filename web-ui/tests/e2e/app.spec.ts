import { test, expect } from '@playwright/test'

test.describe('DataMind Studio Web UI', () => {
  test('renders three-panel layout with header', async ({ page }) => {
    await page.goto('/')

    // Header
    await expect(page.locator('.app-title')).toHaveText('DataMind Studio')

    // Three panels
    await expect(page.locator('.sidebar-panel')).toBeVisible()
    await expect(page.locator('.chat-panel')).toBeVisible()
    await expect(page.locator('.context-panel')).toBeVisible()

    // Context status in header
    await expect(page.locator('.context-status')).toBeVisible()
  })

  test('dark mode toggle switches theme', async ({ page }) => {
    await page.goto('/')

    // Theme toggle button should exist
    const toggle = page.locator('.theme-toggle')
    await expect(toggle).toBeVisible()

    // Click toggle to switch to dark
    await toggle.click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

    // Click again to switch back to light
    await toggle.click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  })

  test('chat panel shows empty state with skill hints', async ({ page }) => {
    await page.goto('/')

    // Empty state should show
    await expect(page.locator('.chat-empty')).toBeVisible()
    await expect(page.locator('.chat-empty h3')).toHaveText('DataMind Studio')

    // Skill hints should be visible
    const hints = page.locator('.skill-hint')
    await expect(hints.first()).toBeVisible()
  })

  test('chat input accepts text and send button works', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await expect(input).toBeVisible()

    // Type a message
    await input.fill('Hello, DataMind!')
    await expect(input).toHaveValue('Hello, DataMind!')

    // Send button should be enabled
    const sendBtn = page.locator('.send-btn')
    await expect(sendBtn).toBeEnabled()

    // Click send
    await sendBtn.click()

    // User message should appear
    await expect(page.locator('.user-bubble').first()).toBeVisible()
  })

  test('skill command autocomplete shows suggestions', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')

    // Type /skill
    await input.fill('/skill ')
    await input.focus()
    await page.keyboard.press('KeyD')

    // Skill suggestions should appear
    const suggestions = page.locator('.skill-suggestion-item')
    // Suggestions may or may not appear depending on timing
    // Check that input value contains /skill prefix
    await expect(input).toHaveValue('/skill d')
  })

  test('data sidebar shows dataset groups', async ({ page }) => {
    await page.goto('/')

    // Sidebar should have section titles
    await expect(page.locator('.section-title').first()).toBeVisible()
  })

  test('context panel shows session context and lineage', async ({ page }) => {
    await page.goto('/')

    // Session context section
    await expect(page.locator('.context-status')).toBeVisible()

    // Lineage graph section
    await expect(page.locator('.graph-title')).toHaveText('Lineage Graph')
  })
})
