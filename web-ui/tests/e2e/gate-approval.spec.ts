import { test, expect } from '@playwright/test'

/**
 * Gate Approval E2E Tests
 *
 * The GateApproval component renders when a ChatMessage has a `gate` property.
 * Because the SSE stream does not currently emit `gate` events (the chat_stream
 * endpoint only emits token/done/error events), the gate UI cannot be reached
 * through normal chat flow.  These tests inject a gate message into the Pinia
 * store via page.evaluate() to exercise the GateApproval component inside the
 * running app.
 *
 * Selectors (from GateApproval.vue):
 *   .gate-prompt       — gate container with approve/reject buttons
 *   .gate-btn.approve  — approve button
 *   .gate-btn.reject   — reject button
 *   .gate-decided.approved — post-approval state
 *   .gate-decided.rejected — post-rejection state
 *   .gate-title        — "Gate: {phase_name}"
 *   .gate-context      — description text
 */

const GATE_PAYLOAD = {
  phase_id: 'confirm-strategy',
  phase_name: 'Confirm Strategy',
  context: 'Review the proposed data exploration approach before execution.',
  session_dir: '/tmp/datamind/sessions/test-gate-session',
}

/**
 * Push a ChatMessage with a `gate` property into the Pinia session store.
 * Returns the message id.
 */
async function injectGateMessage(page: import('@playwright/test').Page, overrides: Record<string, unknown> = {}) {
  const payload = { ...GATE_PAYLOAD, ...overrides }
  return page.evaluate((gate) => {
    const app = (document.querySelector('#app') as any).__vue_app__
    const pinia = app.config.globalProperties.$pinia
    const store = pinia._s.get('session')
    const id = 'e2e-gate-' + Date.now()
    store.messages.push({
      id,
      role: 'ai',
      content: 'I have analyzed the dataset and prepared a strategy for your review.',
      timestamp: Date.now(),
      gate,
      skill_name: 'data-exploration',
    })
    return id
  }, payload)
}

test.describe('Gate Approval Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Route /api/* — bridge SSE streaming to real backend, mock everything else.
    await page.route('**/api/**', async (route) => {
      const url = route.request().url()

      // Redirect streaming to the real FastAPI endpoint (Vite proxy fix)
      if (url.includes('/api/chat/stream')) {
        const newUrl = url.replace('/api/chat/stream', '/chat/stream')
        const response = await route.fetch({ url: newUrl })
        await route.fulfill({ response })
        return
      }

      // Mock /api/skill/gate — the gate decision endpoint
      if (url.includes('/api/skill/gate')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ phase: 'execute', result: null }),
        })
        return
      }

      // Mock data endpoints (app handles failures gracefully)
      if (url.includes('/api/datasets')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/skills')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/decisions')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
      } else if (url.includes('/api/context')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{"ready":true}' })
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
      }
    })
  })

  // -----------------------------------------------------------------------
  // Test 1: Gate appears when skill reaches GATE phase
  // -----------------------------------------------------------------------
  test('gate prompt renders when skill reaches GATE phase', async ({ page }) => {
    await page.goto('/')

    // Initially no gate should be visible
    await expect(page.locator('.gate-prompt')).toHaveCount(0)

    // Inject a gate message into the store
    await injectGateMessage(page)

    // Gate prompt should now be visible with correct content
    const prompt = page.locator('.gate-prompt')
    await expect(prompt.first()).toBeVisible()

    // Title should show the phase name
    await expect(page.locator('.gate-title').first()).toContainText('Confirm Strategy')

    // Context message should be displayed
    await expect(page.locator('.gate-context').first()).toContainText('data exploration')

    // Both approve and reject buttons should be visible and enabled
    const approveBtn = page.locator('.gate-btn.approve').first()
    const rejectBtn = page.locator('.gate-btn.reject').first()
    await expect(approveBtn).toBeVisible()
    await expect(approveBtn).toBeEnabled()
    await expect(rejectBtn).toBeVisible()
    await expect(rejectBtn).toBeEnabled()
  })

  // -----------------------------------------------------------------------
  // Test 2: Approve continues execution past gate
  // -----------------------------------------------------------------------
  test('approve button transitions to approved state', async ({ page }) => {
    await page.goto('/')
    await injectGateMessage(page)

    const approveBtn = page.locator('.gate-btn.approve').first()
    await expect(approveBtn).toBeVisible()

    // Click approve
    await approveBtn.click()

    // The component sets decided='approved' immediately (before API response).
    // The gate prompt is replaced by the decided indicator.
    await expect(page.locator('.gate-decided.approved').first()).toBeVisible()

    // The gate prompt should be gone
    await expect(page.locator('.gate-prompt')).toHaveCount(0)

    // A system message should eventually appear after the mocked API responds.
    // The approveGate function in useChat calls /api/skill/gate then adds a
    // system message with "Gate approved" text.
    await expect(async () => {
      const sysMsg = page.locator('.system-bubble')
      const text = await sysMsg.first().textContent()
      expect(text).toContain('Gate approved')
    }).toPass({ timeout: 10_000 })
  })

  // -----------------------------------------------------------------------
  // Test 3: Reject routes to alternative path
  // -----------------------------------------------------------------------
  test('reject button transitions to rejected state', async ({ page }) => {
    await page.goto('/')
    await injectGateMessage(page)

    const rejectBtn = page.locator('.gate-btn.reject').first()
    await expect(rejectBtn).toBeVisible()

    // Click reject
    await rejectBtn.click()

    // The component sets decided='rejected' immediately
    await expect(page.locator('.gate-decided.rejected').first()).toBeVisible()

    // The gate prompt should be gone
    await expect(page.locator('.gate-prompt')).toHaveCount(0)

    // A system message should eventually appear with rejection text
    await expect(async () => {
      const sysMsg = page.locator('.system-bubble')
      const text = await sysMsg.first().textContent()
      expect(text).toContain('Gate rejected')
    }).toPass({ timeout: 10_000 })
  })

  // -----------------------------------------------------------------------
  // Test 4: Decision record updates after gate approval
  // -----------------------------------------------------------------------
  test('decision record is stored after gate approval', async ({ page }) => {
    await page.goto('/')
    await injectGateMessage(page)

    // Approve the gate
    await page.locator('.gate-btn.approve').first().click()

    // Wait for the system message confirming approval
    await expect(async () => {
      const sysMsg = page.locator('.system-bubble')
      const text = await sysMsg.first().textContent()
      expect(text).toContain('Gate approved')
    }).toPass({ timeout: 10_000 })

    // Verify a system message was added to the store (role === 'system')
    const systemCount = await page.evaluate(() => {
      const app = (document.querySelector('#app') as any).__vue_app__
      const pinia = app.config.globalProperties.$pinia
      const store = pinia._s.get('session')
      return store.messages.filter((m: any) => m.role === 'system').length
    })
    expect(systemCount).toBeGreaterThanOrEqual(1)

    // Verify the gate message no longer shows the prompt (decided state)
    const decidedIndicator = page.locator('.gate-decided.approved').first()
    await expect(decidedIndicator).toBeVisible()
    await expect(decidedIndicator).toContainText('Approved')
  })

  // -----------------------------------------------------------------------
  // Test 5: Gate prompt handles multiple gates
  // -----------------------------------------------------------------------
  test('multiple gate messages each render their own prompt', async ({ page }) => {
    await page.goto('/')

    // Inject two different gate messages
    await injectGateMessage(page, {
      phase_id: 'confirm-strategy',
      phase_name: 'Confirm Strategy',
    })
    await injectGateMessage(page, {
      phase_id: 'review-results',
      phase_name: 'Review Results',
      context: 'Check the model output before generating the report.',
    })

    // Both gate prompts should appear
    const prompts = page.locator('.gate-prompt')
    await expect(prompts).toHaveCount(2)

    // Titles should be different
    const titles = page.locator('.gate-title')
    await expect(titles.first()).toContainText('Confirm Strategy')
    await expect(titles.last()).toContainText('Review Results')
  })

  // -----------------------------------------------------------------------
  // Test 6: Comment textarea is editable
  // -----------------------------------------------------------------------
  test('gate comment textarea accepts input', async ({ page }) => {
    await page.goto('/')
    await injectGateMessage(page)

    const textarea = page.locator('.gate-input').first()
    await expect(textarea).toBeVisible()

    // Type a comment
    await textarea.fill('Looks good, proceed with this plan.')
    await expect(textarea).toHaveValue('Looks good, proceed with this plan.')
  })
})
