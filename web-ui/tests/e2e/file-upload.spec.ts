import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURES = path.resolve(__dirname, 'fixtures')

/**
 * Mock API routes for an upload test.
 * Tracks uploads so that GET /api/datasets returns the uploaded file,
 * preventing fetchDatasets() from overwriting the locally-added dataset.
 */
async function mockUploadApi(page: Page, uploadedFilename: string) {
  await page.route('**/api/**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()

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
    } else if (url.includes('/api/datasets')) {
      // Return the uploaded dataset so fetchDatasets() doesn't clear it
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
    } else if (url.includes('/api/skills')) {
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

test.describe('File Upload', () => {
  test('uploads CSV via file input and dataset appears', async ({ page }) => {
    await mockUploadApi(page, 'sample.csv')
    await page.goto('/')
    const fileInput = page.locator('input[type="file"]')
    const csvPath = path.join(FIXTURES, 'sample.csv')
    await fileInput.setInputFiles(csvPath)
    await expect(page.locator('.dataset-name', { hasText: 'sample.csv' })).toBeVisible({ timeout: 15_000 })
  })

  test('uploads Excel file and dataset appears', async ({ page }) => {
    await mockUploadApi(page, 'sample.xlsx')
    await page.goto('/')
    const fileInput = page.locator('input[type="file"]')
    const xlsxPath = path.join(FIXTURES, 'sample.xlsx')
    await fileInput.setInputFiles(xlsxPath)
    await expect(page.locator('.dataset-name', { hasText: 'sample.xlsx' })).toBeVisible({ timeout: 15_000 })
  })

  test('uploads Parquet file and dataset appears', async ({ page }) => {
    await mockUploadApi(page, 'sample.parquet')
    await page.goto('/')
    const fileInput = page.locator('input[type="file"]')
    const pqPath = path.join(FIXTURES, 'sample.parquet')
    await fileInput.setInputFiles(pqPath)
    await expect(page.locator('.dataset-name', { hasText: 'sample.parquet' })).toBeVisible({ timeout: 15_000 })
  })

  test('invalid file format shows error or fallback', async ({ page }) => {
    // For invalid upload, mock upload to return an error
    await page.route('**/api/**', async (route) => {
      const url = route.request().url()
      const method = route.request().method()

      if (url.includes('/api/upload') && method === 'POST') {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Unsupported file format: .txt' }),
        })
      } else if (url.includes('/api/datasets')) {
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

    await page.goto('/')
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'invalid.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('this is not a valid data file'),
    })
    // Verify the upload error UI appears with the error detail from the API
    const errorEl = page.locator('.upload-error')
    await expect(errorEl).toBeVisible({ timeout: 10_000 })
    await expect(errorEl).toContainText('Unsupported file format: .txt')
  })
})
