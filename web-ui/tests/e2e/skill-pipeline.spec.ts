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
  context: 'Review the proposed approach before execution.',
  session_dir: '/tmp/datamind/sessions/test-skill-pipeline',
}

const SKILLS = ['data-exploration', 'data-cleaning', 'feature-engineering', 'model-training'] as const

/**
 * Push a ChatMessage with a `gate` property into the Pinia session store.
 */
async function injectGateMessage(
  page: Page,
  skillName: string,
  overrides: Record<string, unknown> = {},
): Promise<string> {
  const payload = { ...GATE_PAYLOAD, ...overrides }
  return page.evaluate(({ gate, skill }) => {
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
      skill_name: skill,
    })
    return id
  }, { gate: payload, skill: skillName })
}

/**
 * Run one skill phase: send command, wait for real API streaming, inject gate, approve.
 * Returns the AI bubble text content.
 */
async function runSkillPhase(
  page: Page,
  skillName: string,
  target: string,
): Promise<string> {
  // Type the skill command and send
  const input = page.locator('.chat-input')
  await expect(input).toBeVisible()
  await input.fill(`/skill ${skillName} --target ${target}`)
  await page.locator('.send-btn').click()

  // User bubble should appear immediately
  await expect(page.locator('.user-bubble').first()).toBeVisible()

  // Streaming starts — stop button replaces send button
  await expect(page.locator('.stop-btn')).toBeVisible({ timeout: 10_000 })

  // Wait for streaming to finish (stop button disappears)
  await expect(page.locator('.stop-btn')).toBeHidden({ timeout: 120_000 })

  // AI bubble should have content from real API
  const aiBubble = page.locator('.ai-bubble').first()
  await expect(aiBubble).toBeVisible()
  const aiContent = await aiBubble.textContent()
  expect(aiContent).toBeTruthy()

  // Skill tag should appear on the most recent message (use .last() because
  // previous skill invocations already added tags to the DOM)
  await expect(page.locator('.skill-tag').last()).toContainText(skillName)

  // Inject gate message (SSE parser does not emit gate events)
  await injectGateMessage(page, skillName)

  // Gate prompt should be visible
  const gatePrompt = page.locator('.gate-prompt').first()
  await expect(gatePrompt).toBeVisible()

  // Approve the gate
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

  return aiContent || ''
}

test.describe('Skill Pipeline - Full 4-Skill Chain (Real DeepSeek API)', () => {
  test.setTimeout(600_000)

  test.beforeEach(async ({ page }) => {
    /**
     * Mock all /api/* routes except /api/chat/stream, which is redirected
     * to the real FastAPI backend via route.continue() for SSE streaming.
     *
     * CRITICAL: route.continue({ url: newUrl }) streams the response without
     * buffering. route.fetch() + route.fulfill() would buffer the entire body
     * and deadlock SSE.
     */
    await page.route('**/api/**', async (route) => {
      const url = route.request().url()
      const method = route.request().method()

      // Redirect SSE streaming to the real backend endpoint.
      if (url.includes('/api/chat/stream')) {
        const newUrl = url.replace('/api/chat/stream', '/chat/stream')
        await route.continue({ url: newUrl })
        return
      }

      // File upload
      if (url.includes('/api/upload') && method === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            filename: 'sample.csv',
            path: '/data/uploads/sample.csv',
            rows: 100,
            columns: 7,
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
              id: 'sample.csv',
              name: 'sample.csv',
              path: '/data/uploads/sample.csv',
              file_type: 'csv',
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
  })

  // -----------------------------------------------------------------------
  // Test 1: Full 4-skill pipeline — CSV → data-exploration → data-cleaning
  //         → feature-engineering → model-training (real DeepSeek API)
  // -----------------------------------------------------------------------
  test('CSV upload -> 4-skill sequential chain with real DeepSeek API', async ({ page }) => {
    await page.goto('/')

    // Step 1 — Upload CSV via file input (DataSidebar component)
    const fileInput = page.locator('input[type="file"]')
    const csvPath = path.join(FIXTURES, 'sample.csv')
    await fileInput.setInputFiles(csvPath)

    // Dataset name should appear in sidebar after upload + fetchDatasets
    await expect(
      page.locator('.dataset-name', { hasText: 'sample.csv' }),
    ).toBeVisible({ timeout: 15_000 })

    // Step 2 — Run all 4 skills sequentially
    const target = 'web-ui/tests/e2e/fixtures/sample.csv'

    for (const skill of SKILLS) {
      const aiContent = await runSkillPhase(page, skill, target)

      // Verify the AI response is substantial (real API generates meaningful content)
      expect(aiContent.replace(/\|/g, '').trim().length).toBeGreaterThan(20)

      // Input should be cleared after each completion
      await expect(page.locator('.chat-input')).toHaveValue('')
    }

    // After full pipeline, context-status should still be visible
    await expect(page.locator('.header-right .context-status')).toBeVisible()
  })

  // -----------------------------------------------------------------------
  // Test 2: Pipeline preserves context across phases
  // -----------------------------------------------------------------------
  test('pipeline preserves context status and skill tags across phases', async ({ page }) => {
    await page.goto('/')

    // Verify context-status is visible in header at the start
    const headerContext = page.locator('.header-right .context-status')
    await expect(headerContext).toBeVisible()
    await expect(headerContext).toContainText('Context')

    const target = 'web-ui/tests/e2e/fixtures/sample.csv'

    // Run data-exploration
    await runSkillPhase(page, 'data-exploration', target)

    // Context status should still be visible after first skill
    await expect(page.locator('.header-right .context-status')).toBeVisible()

    // Skill tag should persist in the chat
    await expect(page.locator('.skill-tag').first()).toContainText('data-exploration')

    // Run data-cleaning
    await runSkillPhase(page, 'data-cleaning', target)

    // After second skill, skill tags from both AI responses and gate messages
    // are present. Each skill creates 2 tags (AI bubble + injected gate message).
    const skillTags = page.locator('.skill-tag')
    // At least 2 tags should exist (one per real AI response)
    const tagCount = await skillTags.count()
    expect(tagCount).toBeGreaterThanOrEqual(2)
    await expect(skillTags.first()).toContainText('data-exploration')
    await expect(skillTags.last()).toContainText('data-cleaning')

    // Context status should still be visible
    await expect(page.locator('.header-right .context-status')).toBeVisible()
  })

  // -----------------------------------------------------------------------
  // Test 3: Skill completion shows result summary and resets input
  // -----------------------------------------------------------------------
  test('skill completion shows AI result summary and resets input', async ({ page }) => {
    await page.goto('/')

    const target = 'web-ui/tests/e2e/fixtures/sample.csv'

    // Run data-exploration skill and verify completion behavior
    await runSkillPhase(page, 'data-exploration', target)

    // After completion, the input should be empty
    const input = page.locator('.chat-input')
    await expect(input).toHaveValue('')

    // Send button should be visible (replaces stop button after streaming)
    await expect(page.locator('.send-btn')).toBeVisible()

    // AI bubble should contain substantive analysis from real DeepSeek API.
    // The real model should produce a data exploration report mentioning columns,
    // statistics, or dataset characteristics.
    const aiBubble = page.locator('.ai-bubble').first()
    const content = await aiBubble.textContent()
    expect(content).toBeTruthy()

    // Check for common data exploration output patterns from real model
    const contentLower = (content || '').toLowerCase()
    const hasAnalysisMarkers =
      contentLower.includes('column') ||
      contentLower.includes('row') ||
      contentLower.includes('data') ||
      contentLower.includes('statistic') ||
      contentLower.includes('summary') ||
      contentLower.includes('dataset') ||
      contentLower.includes('analysis')
    expect(hasAnalysisMarkers).toBe(true)
  })
})
