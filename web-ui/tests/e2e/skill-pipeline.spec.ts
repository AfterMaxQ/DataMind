import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURES = path.resolve(__dirname, 'fixtures')

/**
 * Gate payload matching the GatePrompt interface.
 * Injected via Pinia store because the SSE stream does not emit `gate` events
 * (only token/done/error) — same pattern as gate-approval.spec.ts.
 */
const GATE_PAYLOAD = {
  phase_id: 'confirm-strategy',
  phase_name: 'Confirm Strategy',
  context: 'Review the proposed data exploration approach before execution.',
  session_dir: '/tmp/datamind/sessions/test-skill-pipeline',
}

/**
 * Push a ChatMessage with a `gate` property into the Pinia session store.
 */
async function injectGateMessage(
  page: Page,
  overrides: Record<string, unknown> = {},
): Promise<string> {
  const payload = { ...GATE_PAYLOAD, ...overrides }
  return page.evaluate((gate) => {
    const app = (document.querySelector('#app') as any).__vue_app__
    const pinia = app.config.globalProperties.$pinia
    const store = pinia._s.get('session')
    const id = 'e2e-pipeline-gate-' + Date.now()
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

/**
 * Simulate an SSE token stream so tests are self-contained.
 * The frontend parser (useChat.ts) expects lines like:
 *   data: {"content": "<token>"}\n\n
 */
function buildMockSseBody(tokens: string[]): string {
  return tokens.map((t) => `data: ${JSON.stringify({ content: t })}\n\n`).join('')
}

const SSE_TOKENS = [
  'I', ' have', ' analyzed', ' the', ' dataset', ' and', ' here', ' are', ' the', ' results', ':',
  '\n\n',
  '##', ' Summary', '\n',
  '-', ' **', 'Rows', ':**', ' 100', '\n',
  '-', ' **', 'Columns', ':**', ' 5', ' (', 'id', ',', ' name', ',', ' age', ',', ' city', ',', ' salary', ')', '\n',
  '-', ' **', 'Missing', ' values', ':**', ' 0', '\n',
  '-', ' **', 'Salary', ' range', ':**', ' 48', ',', '316', ' –', ' 176', ',', '225', '\n',
]

/** SSE body pre-built once. `buildMockSseBody` adds the "data:" prefix to construct SSE wire format. */
const MOCK_SSE_BODY = buildMockSseBody(SSE_TOKENS)

/**
 * Mock all /api/* routes for the skill pipeline flow.
 * - /api/chat/stream → returns simulated SSE token stream
 * - /api/upload → accepts file uploads
 * - /api/skill/gate → returns gate decision
 * - All others → mock with sensible defaults
 */
async function mockPipelineApi(page: Page, uploadedFilename = 'sample.csv') {
  await page.route('**/api/**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()

    // Return simulated SSE token stream (self-contained, no real API dependency).
    // A small delay keeps the stop-btn → send-btn transition observable.
    if (url.includes('/api/chat/stream')) {
      await new Promise((r) => setTimeout(r, 400))
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
        body: MOCK_SSE_BODY,
      })
      return
    }

    // File upload
    if (url.includes('/api/upload') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          filename: uploadedFilename,
          path: `/data/uploads/${uploadedFilename}`,
          rows: 100,
          columns: 5,
        }),
      })
      return
    }

    // Gate decision endpoint
    if (url.includes('/api/skill/gate')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ phase: 'execute', result: null }),
      })
      return
    }

    // Return uploaded dataset so fetchDatasets() doesn't clear it
    if (url.includes('/api/datasets')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: uploadedFilename,
            name: uploadedFilename,
            path: `/data/uploads/${uploadedFilename}`,
            file_type: uploadedFilename.split('.').pop(),
          },
        ]),
      })
      return
    }

    if (url.includes('/api/skills')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    } else if (url.includes('/api/decisions')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    } else if (url.includes('/api/context')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ready: true, datasets: 1, decisions: 0 }),
      })
    } else {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
    }
  })
}

test.describe('Skill Pipeline - Full E2E Flow', () => {
  test.setTimeout(180_000)

  // -----------------------------------------------------------------------
  // Test 1: CSV upload → data-exploration skill → gate → result
  // -----------------------------------------------------------------------
  test('CSV upload -> data-exploration skill -> gate -> result', async ({ page }) => {
    await mockPipelineApi(page, 'sample.csv')
    await page.goto('/')

    // Step 1 — Upload CSV via file input (DataSidebar component)
    const fileInput = page.locator('input[type="file"]')
    const csvPath = path.join(FIXTURES, 'sample.csv')
    await fileInput.setInputFiles(csvPath)

    // Dataset name should appear in sidebar after upload + fetchDatasets
    await expect(
      page.locator('.dataset-name', { hasText: 'sample.csv' }),
    ).toBeVisible({ timeout: 15_000 })

    // Step 2 — Send skill command
    const input = page.locator('.chat-input')
    await expect(input).toBeVisible()
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    // Step 3 — Wait for AI response via streaming (mock SSE)
    // The user bubble should appear immediately
    await expect(page.locator('.user-bubble').first()).toBeVisible()

    // Stream starts → stop button replaces send button
    await expect(page.locator('.stop-btn')).toBeVisible({ timeout: 10_000 })

    // Wait for streaming to finish (stop button disappears)
    await expect(page.locator('.stop-btn')).toBeHidden({ timeout: 90_000 })

    // AI bubble should have content
    const aiBubble = page.locator('.ai-bubble').first()
    await expect(aiBubble).toBeVisible()
    const aiContent = await aiBubble.textContent()
    expect(aiContent).toBeTruthy()

    // Skill tag should appear on the message
    await expect(page.locator('.skill-tag').first()).toContainText('data-exploration')

    // Step 4 — Inject gate message (SSE parser does not emit gate events)
    await injectGateMessage(page)

    // Gate prompt should be visible
    const gatePrompt = page.locator('.gate-prompt').first()
    await expect(gatePrompt).toBeVisible()
    await expect(page.locator('.gate-title').first()).toContainText('Confirm Strategy')

    // Step 5 — Approve the gate
    const approveBtn = page.locator('.gate-btn.approve').first()
    await expect(approveBtn).toBeEnabled()
    await approveBtn.click()

    // Gate transitions to approved state
    await expect(page.locator('.gate-decided.approved').first()).toBeVisible()
    await expect(page.locator('.gate-prompt')).toHaveCount(0)

    // System message confirms gate approval
    await expect(async () => {
      const sysMsg = page.locator('.system-bubble')
      const text = await sysMsg.first().textContent()
      expect(text).toContain('Gate approved')
    }).toPass({ timeout: 10_000 })
  })

  // -----------------------------------------------------------------------
  // Test 2: Pipeline preserves context across phases
  // -----------------------------------------------------------------------
  test('pipeline preserves context across phases', async ({ page }) => {
    await mockPipelineApi(page)
    await page.goto('/')

    // Verify context-status is visible in header (App.vue — .header-right to avoid
    // strict-mode violation with ContextPanel.vue's .context-status div)
    const headerContext = page.locator('.header-right .context-status')
    await expect(headerContext).toBeVisible()
    await expect(headerContext).toContainText('Context')

    // Send skill command
    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    // Wait for AI response
    const aiBubble = page.locator('.ai-bubble').first()
    await expect(aiBubble).toBeVisible({ timeout: 60_000 })

    // Content should be non-empty
    await expect(async () => {
      const content = await aiBubble.textContent()
      expect(content).toBeTruthy()
      expect(content!.replace(/\|/g, '').trim().length).toBeGreaterThan(0)
    }).toPass({ timeout: 90_000 })

    // Skill tag should be present
    await expect(page.locator('.skill-tag').first()).toBeVisible()

    // Context status should still be visible after pipeline activity
    await expect(page.locator('.header-right .context-status')).toBeVisible()
  })

  // -----------------------------------------------------------------------
  // Test 3: Skill completion shows result summary
  // -----------------------------------------------------------------------
  test('skill completion shows result summary', async ({ page }) => {
    await mockPipelineApi(page)
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    // Streaming starts
    await expect(page.locator('.stop-btn')).toBeVisible({ timeout: 10_000 })

    // Wait for streaming to complete
    await expect(page.locator('.stop-btn')).toBeHidden({ timeout: 90_000 })

    // AI bubble should have substantial content
    const aiBubble = page.locator('.ai-bubble').first()
    await expect(aiBubble).toBeVisible()

    const content = await aiBubble.textContent()
    expect(content).toBeTruthy()

    // Stream completed — input should be cleared, send button back
    await expect(input).toHaveValue('')
    await expect(page.locator('.send-btn')).toBeVisible()

    // Inject gate to verify post-gate state also works in pipeline context
    await injectGateMessage(page)

    const approveBtn = page.locator('.gate-btn.approve').first()
    await expect(approveBtn).toBeVisible()
    await approveBtn.click()

    await expect(page.locator('.gate-decided.approved').first()).toBeVisible()

    // System message appears after gate decision
    await expect(async () => {
      const sysMsg = page.locator('.system-bubble')
      const text = await sysMsg.first().textContent()
      expect(text).toContain('Gate approved')
    }).toPass({ timeout: 10_000 })
  })
})
