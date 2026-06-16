# DataMind Studio Testing Runbook

## Overview

DataMind Studio has two test suites:

1. **Python backend tests** (321+ tests, pytest) -- unit + integration
2. **Playwright E2E tests** (7 spec files, 20+ tests, @playwright/test) -- browser automation against the full app stack

The E2E tests connect to a FastAPI server on **port 9003** (changed from the originally planned 9000 due to a MinIO port conflict).

---

## Prerequisites

### Python Tests

- Python 3.11+
- Install: `pip install -e "."`

### Playwright E2E Tests

- Node.js 18+ (working directory: `web-ui/`)
- Install: `npm ci`
- Chromium browser: `npx playwright install chromium`
- DeepSeek API key (for interaction tests only; rendering tests use mocked APIs)

---

## Running Tests

### Quick Start

```bash
# All Python tests
pytest -v

# All Playwright E2E tests
cd web-ui && npx playwright test

# Both suites together
pytest -v && cd web-ui && npx playwright test
```

### Python Test Commands

```bash
# Full suite
pytest -v

# Run quietly (summary only)
pytest -q

# Specific areas
pytest tests/unit/test_tools.py -v
pytest tests/unit/test_json_formatter.py -v
pytest tests/unit/test_tool_tracing.py -v
pytest tests/unit/test_debug_endpoints.py -v
pytest tests/unit/test_data_model.py -v

# With coverage
pytest --cov=datamind --cov-report=term-missing

# Fail-fast on first error
pytest -x

# Verbose with local variable output on failure
pytest -v --tb=long
```

### Playwright E2E Commands

All Playwright commands run from `web-ui/`:

```bash
cd web-ui

# All E2E tests
npx playwright test

# Specific spec file
npx playwright test app.spec.ts

# Multiple specific files
npx playwright test websocket.spec.ts streaming.spec.ts

# UI mode (interactive debugging, step through tests visually)
npx playwright test --ui

# Headed mode (see browser window)
npx playwright test --headed

# Headed + slow motion (500ms delay between actions)
npx playwright test --headed --slow-mo=500

# Generate and view HTML report
npx playwright test --reporter=html
npx playwright show-report

# List available tests without running
npx playwright test --list

# Run only rendering tests (no API key needed)
npx playwright test app.spec.ts websocket.spec.ts

# Run with custom base URL
PLAYWRIGHT_BASE_URL=http://127.0.0.1:9003 npx playwright test
```

---

## Test Categories

### Rendering Tests (Mock API)

Tests that verify the UI renders correctly. All API calls are intercepted and mocked -- **no DeepSeek API key required**. These are fast (< 10s total).

| Spec File | What It Tests |
|-----------|---------------|
| `app.spec.ts` | Three-panel layout, dark mode toggle, chat input, skill autocomplete, sidebar datasets, context panel, lineage graph (7 tests) |
| `websocket.spec.ts` | WebSocket connection indicator, reconnect after page reload, SPA navigation persistence, sidebar section visibility (4 tests) |

Mocking strategy: `page.route('**/api/**')` intercepts frontend API calls. `route.fulfill()` returns canned JSON responses.

### Interaction Tests (Real API)

Tests that exercise the full stack with a running FastAPI server on port 9003. **DeepSeek API key required** (set via `DATAMIND_API_KEY` or `DEEPSEEK_API_KEY`). These are slower -- each test can take 10-90s.

| Spec File | What It Tests | Key Required |
|-----------|---------------|--------------|
| `streaming.spec.ts` | SSE token-by-token streaming, `/skill` command input, send button resets after stream completes (3 tests) | Yes |
| `gate-approval.spec.ts` | Gate appears at phase boundary, approve continues execution, reject shows rejection state, decision record updates (4 tests) | Yes |
| `file-upload.spec.ts` | CSV/Excel/Parquet upload, dataset display, invalid file handling (4 tests) | No |
| `skill-pipeline.spec.ts` | Full pipeline: CSV upload -> exploration skill -> gate -> result, context preservation, completion summary (3 tests) | Yes |
| `error-scenarios.spec.ts` | Empty message rejection, invalid file format, rapid message stress, network error during stream, long response UI freeze (5 tests) | Yes |

**SSE streaming note**: The streaming and skill-pipeline specs use `route.continue()` to pass requests through to the real FastAPI backend without buffering. `route.fetch()` + `route.fulfill()` would buffer the entire SSE response body and deadlock. This is a critical implementation detail -- do not change this pattern.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATAMIND_PROVIDER` | `deepseek` | LLM provider name |
| `DATAMIND_MODEL` | `deepseek-v4-flash` | LLM model identifier |
| `DATAMIND_API_KEY` | (from config) | API key for LLM provider |
| `DATAMIND_API_BASE` | `https://api.deepseek.com` | API base URL |
| `DATAMIND_LOG_LEVEL` | `INFO` | Log verbosity: DEBUG, INFO, WARNING, ERROR |
| `DATAMIND_DEBUG_DISABLE` | (not set) | Set to `1` to disable `/debug/*` endpoints |

The Playwright config (`playwright.config.ts`) reads `DEEPSEEK_API_KEY` from the environment and injects it as `DATAMIND_API_KEY` into the server process:

```typescript
env: {
  DATAMIND_PROVIDER: 'deepseek',
  DATAMIND_MODEL: 'deepseek-v4-flash',
  DATAMIND_API_KEY: process.env.DEEPSEEK_API_KEY,
  DATAMIND_API_BASE: 'https://api.deepseek.com'
},
```

So you can export either variable:

```bash
# EITHER
export DEEPSEEK_API_KEY=sk-...
# OR (the Playwright config maps this to DATAMIND_API_KEY)
export DATAMIND_API_KEY=sk-...
```

---

## CI Integration (GitHub Actions)

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install Python dependencies
        run: pip install -e "."

      - name: Run Python tests
        run: pytest -q

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: web-ui/package-lock.json

      - name: Install Playwright
        run: |
          cd web-ui
          npm ci
          npx playwright install chromium --with-deps

      - name: Run Playwright E2E tests
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
        run: |
          cd web-ui
          npx playwright test

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: web-ui/playwright-report/
          retention-days: 7
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| All E2E tests timeout | FastAPI not starting on port 9003 | Verify `webServer` config in `playwright.config.ts`. Check that port 9003 is free. |
| Port 9003 already in use | Previous test run or MinIO did not terminate | `npx kill-port 9003` or find the process with `netstat -ano \| findstr :9003` (Windows) / `lsof -i :9003` (macOS/Linux) |
| Streaming tests fail with empty responses | DeepSeek API key invalid or missing | Verify `DEEPSEEK_API_KEY` or `DATAMIND_API_KEY` env var is set. Check API key validity. |
| Streaming tests hang indefinitely | SSE deadlock from wrong route pattern | Verify `route.continue()` is used for `/chat/stream` routes, NOT `route.fetch()` + `route.fulfill()`. The latter buffers SSE and causes deadlocks. |
| Chromium not found | Playwright browsers not installed | Run `npx playwright install chromium` |
| Playwright exits with `Executable doesn't exist` | Missing system dependencies | Run `npx playwright install chromium --with-deps` |
| Python tests fail after logging changes | Logger handler conflicts or state leakage | Check that tests using the root logger clean up their handlers. Run failing test in isolation: `pytest path/to/test.py -v` |
| `ModuleNotFoundError` in tests | Package not installed in development mode | Run `pip install -e "."` |
| Gate approval tests fail with 404 | Debug endpoints disabled or route not mounted | Check `DATAMIND_DEBUG_DISABLE` is not set. Verify `debug_router` is included in `app.py`. |
| File upload tests fail | `uploads/` directory missing or not writable | Ensure the server's working directory has write permissions. Check `MAX_UPLOAD_SIZE` setting. |
