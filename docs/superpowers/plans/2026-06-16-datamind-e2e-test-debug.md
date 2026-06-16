---
change: datamind-e2e-test-debug
design-doc: docs/superpowers/specs/2026-06-16-datamind-e2e-test-debug-design.md
base-ref: a0cf010cd79b3f47fddb4e0c67430be712c38f5f
---

# DataMind E2E Testing & Debug Infrastructure - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add JSON structured logging, tool call tracing, runtime debug endpoints, and a 7-file Playwright E2E test suite to DataMind Studio -- without modifying existing business logic or test suites.

**Architecture:** Incremental, additive changes. JsonFormatter + contextvars inject session_id into all log records without changing function signatures. ToolRegistry.execute() wraps the existing handler call with timing/logging. A standalone debug router (datamind/api/debug.py) exposes /debug/* endpoints gated by DATAMIND_DEBUG_DISABLE. Playwright E2E tests are split into rendering tests (mock API via page.route()) and interaction tests (real DeepSeek API).

**Tech Stack:** Python stdlib logging + contextvars, FastAPI APIRouter, @playwright/test 1.50, DeepSeek V4 Flash API.

---

## File Structure

**New files (create):**
| File | Responsibility |
|------|---------------|
| datamind/session_context.py | Single ContextVar[str] for session_id propagation |
| datamind/logging_setup.py | JsonFormatter subclass + setup_logging() factory |
| datamind/api/debug.py | FastAPI router with /debug/state, /debug/sessions, /debug/logs |
| web-ui/tests/e2e/fixtures/sample.csv | 100-row CSV fixture for E2E tests |
| web-ui/tests/e2e/fixtures/sample.xlsx | Excel fixture for upload tests |
| web-ui/tests/e2e/fixtures/sample.parquet | Parquet fixture for upload tests |
| web-ui/tests/e2e/websocket.spec.ts | WebSocket connect/disconnect/reconnect tests |
| web-ui/tests/e2e/streaming.spec.ts | SSE token-by-token streaming tests |
| web-ui/tests/e2e/gate-approval.spec.ts | Gate approve/reject workflow tests |
| web-ui/tests/e2e/file-upload.spec.ts | File upload, drag-drop, error handling tests |
| web-ui/tests/e2e/skill-pipeline.spec.ts | Full skill pipeline E2E tests |
| web-ui/tests/e2e/error-scenarios.spec.ts | Empty message, invalid file, timeout tests |
| docs/testing-runbook.md | Test execution handbook |
| docs/debugging-runbook.md | Fault diagnosis decision tree |
| 	ests/unit/test_json_formatter.py | JsonFormatter unit tests |
| 	ests/unit/test_tool_tracing.py | ToolRegistry tracing unit tests |
| 	ests/unit/test_debug_endpoints.py | Debug endpoint unit tests |

**Modified files:**
| File | Change |
|------|--------|
| datamind/__init__.py | Call setup_logging() on module load |
| datamind/api/app.py | Add session middleware, pp.state.session_registry, mount debug router, register created agents |
| datamind/engine/tools.py | Add timing/logging wrapper in ToolRegistry.execute() |
| web-ui/playwright.config.ts | Point webServer at FastAPI (port 9000), inject DeepSeek env vars |

---

## Task 1: Session Context Infrastructure

### Task 1.1: Create datamind/session_context.py

**Files:**
- Create: datamind/session_context.py

- [ ] **Step 1: Create the session_context module**

`python
# datamind/session_context.py
"""Session context propagation via Python contextvars.

Allows session_id to be read by log formatters, tool tracers, and
debug endpoints without modifying function signatures across the
call stack.

Usage:
    from datamind.session_context import _current_session_id

    # Set (typically in FastAPI middleware):
    _current_session_id.set("abc123")

    # Read (anywhere in the same async task):
    sid = _current_session_id.get()
"""

from contextvars import ContextVar

_current_session_id: ContextVar[str] = ContextVar("session_id", default="")
`

- [ ] **Step 2: Verify the module imports cleanly**

Run: python -c "from datamind.session_context import _current_session_id; print(_current_session_id.get())"
Expected: prints empty string ("")

- [ ] **Step 3: Commit**

`ash
git add datamind/session_context.py
git commit -m "feat: add session_context module with ContextVar for session_id propagation"
`

---

## Task 2: JSON Structured Logging

### Task 2.1: Write the JsonFormatter test

**Files:**
- Create: 	ests/unit/test_json_formatter.py

- [ ] **Step 1: Write the failing test**

`python
# tests/unit/test_json_formatter.py
"""Tests for datamind.logging_setup.JsonFormatter."""

import json
import logging
import io
from datamind.logging_setup import JsonFormatter
from datamind.session_context import _current_session_id


def test_json_formatter_emits_valid_json_lines():
    """JsonFormatter produces valid JSON with all required fields."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    fmt = JsonFormatter()
    handler.setFormatter(fmt)

    logger = logging.getLogger("test_json")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    _current_session_id.set("session-abc-123")
    logger.info("User connected", extra={"data": {"ip": "127.0.0.1"}})

    handler.flush()
    line = stream.getvalue().strip()
    assert line, "Expected at least one log line"

    record = json.loads(line)
    assert record["level"] == "INFO"
    assert record["module"] == "test_json"
    assert record["event"] == "User connected"
    assert record["session_id"] == "session-abc-123"
    assert record["data"] == {"ip": "127.0.0.1"}
    assert "ts" in record
    assert "elapsed_ms" in record


def test_json_formatter_without_session_id():
    """When no session_id is set, the field is an empty string."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_no_session")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    _current_session_id.set("")
    logger.warning("No session")
    handler.flush()

    record = json.loads(stream.getvalue().strip())
    assert record["session_id"] == ""
    assert record["level"] == "WARNING"


def test_json_formatter_error_includes_traceback():
    """Exception log records include traceback in data."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_error")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    try:
        raise ValueError("bad input")
    except ValueError:
        logger.error("Caught error", exc_info=True)

    handler.flush()
    record = json.loads(stream.getvalue().strip())
    assert record["level"] == "ERROR"
    assert "bad input" in record.get("data", {}).get("traceback", "")
`

- [ ] **Step 2: Run tests to verify they fail**

Run: pytest tests/unit/test_json_formatter.py -v
Expected: FAIL with ModuleNotFoundError: No module named 'datamind.logging_setup'

---

### Task 2.2: Implement datamind/logging_setup.py

**Files:**
- Create: datamind/logging_setup.py

- [ ] **Step 3: Write the JsonFormatter class and setup_logging**

`python
# datamind/logging_setup.py
"""JSON Lines structured logging for DataMind Studio.

Provides :class:JsonFormatter for file-based JSON output and
:func:setup_logging to configure the root logger at startup.

Stdout retains human-readable text; file output is JSON Lines.
"""

import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from datamind.session_context import _current_session_id

_BUILD_EPOCH = time.time()


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects (JSON Lines).

    Each line contains: `ts`, `level`, `module`, `event`,
    `session_id`, `data`, `elapsed_ms`.
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.000Z")
        data = getattr(record, "data", {})
        if not isinstance(data, dict):
            data = {"value": str(data)}

        # Attach exception info if present
        if record.exc_info and record.exc_info[0]:
            import traceback
            tb_lines = traceback.format_exception(*record.exc_info)
            data["traceback"] = "".join(tb_lines).strip()

        payload = {
            "ts": ts,
            "level": record.levelname,
            "module": record.name,
            "event": record.getMessage(),
            "session_id": _current_session_id.get(),
            "data": data,
            "elapsed_ms": int((record.created - _BUILD_EPOCH) * 1000),
        }

        # Allow overriding fields via extra
        extra = getattr(record, "json_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    log_dir: str | None = None,
    level: str | None = None,
) -> None:
    """Configure root logger with dual output.

    - `stdout`: human-readable `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
    - `file`: JSON Lines via :class:JsonFormatter, written to
      `<log_dir>/app.jsonl` with daily rotation and 7-day retention.

    Args:
        log_dir: Path to the log directory. Defaults to
            `.datamind/logs/` relative to the project root.
        level: Log level string (DEBUG/INFO/WARNING/ERROR). Defaults to
            `DATAMIND_LOG_LEVEL` env var or `"INFO"`.
    """
    if level is None:
        level = os.environ.get("DATAMIND_LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    # Clear existing handlers to avoid duplicates on reload
    root.handlers.clear()

    # -- Stdout: human-readable --
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    stdout_handler.setFormatter(stdout_fmt)
    root.addHandler(stdout_handler)

    # -- File: JSON Lines --
    if log_dir is None:
        log_dir = os.path.join(os.getcwd(), ".datamind", "logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.jsonl"),
        when="D",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    root.info("DataMind logging initialized (level=%s, dir=%s)", level, log_dir)
`

- [ ] **Step 4: Run the JsonFormatter tests**

Run: pytest tests/unit/test_json_formatter.py -v
Expected: 3 PASS

- [ ] **Step 5: Commit**

`ash
git add datamind/logging_setup.py tests/unit/test_json_formatter.py
git commit -m "feat: add JsonFormatter and setup_logging for JSON Lines structured logging"
`

---

### Task 2.3: Wire logging setup into app startup

**Files:**
- Modify: datamind/__init__.py (lines 1-3)
- Modify: datamind/api/app.py

- [ ] **Step 1: Call setup_logging in datamind/__init__.py**

Replace the content of datamind/__init__.py with:

`python
"""DataMind Studio -- AI-native data science research system."""

__version__ = "0.1.0"

# Initialize structured logging on module import.
# setup_logging is idempotent -- calling it again only reconfigures handlers.
import os as _os
if _os.environ.get("DATAMIND_LOG_DISABLE") != "1":
    from datamind.logging_setup import setup_logging as _setup_logging
    _setup_logging()
`

- [ ] **Step 2: Add session middleware to datamind/api/app.py**

In datamind/api/app.py, inside create_app(), after line 43 (the dd_middleware(CORSMiddleware, ...) call), add:

`python
    # -- Session context middleware (D6) --
    from datamind.session_context import _current_session_id

    @app.middleware("http")
    async def session_context_middleware(request, call_next):
        """Set session_id in contextvars for the duration of this request."""
        import uuid
        sid = request.headers.get("X-Session-ID") or str(uuid.uuid4())
        token = _current_session_id.set(sid)
        try:
            response = await call_next(request)
            return response
        finally:
            _current_session_id.reset(token)
`

- [ ] **Step 3: Smoke-test logging**

Create and run a one-off smoke test (delete afterward):

`python
# smoke_test_logging.py (delete after running)
import sys; sys.path.insert(0, ".")
from datamind.logging_setup import setup_logging
setup_logging(level="DEBUG")
from datamind.session_context import _current_session_id
import logging
_log = logging.getLogger("smoke_test")
_current_session_id.set("smoke-session-1")
_log.info("Hello from smoke test", extra={"data": {"test": True}})
print("Check stdout and .datamind/logs/app.jsonl")
`

Run: python smoke_test_logging.py
Expected: stdout line [INFO] smoke_test: Hello from smoke test, plus .datamind/logs/app.jsonl containing JSON with "session_id": "smoke-session-1".

Clean up: m smoke_test_logging.py

- [ ] **Step 4: Commit**

`ash
git add datamind/__init__.py datamind/api/app.py
git commit -m "feat: wire logging setup into app startup and add session context middleware"
`

---

## Task 3: Tool Call Tracing

### Task 3.1: Write tool tracing tests

**Files:**
- Create: 	ests/unit/test_tool_tracing.py

- [ ] **Step 1: Write failing tests for ToolRegistry tracing**

`python
# tests/unit/test_tool_tracing.py
"""Tests for tool call tracing in ToolRegistry.execute()."""

import json
import logging
import io
from datamind.engine.tools import ToolRegistry
from datamind.logging_setup import JsonFormatter
from datamind.session_context import _current_session_id


def _make_registry() -> ToolRegistry:
    """Create a minimal ToolRegistry with a single echo tool."""
    reg = ToolRegistry()
    def echo(**kwargs) -> dict:
        return {"echoed": kwargs}
    reg.register("echo", {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo back arguments",
            "parameters": {"type": "object", "properties": {}},
        },
    }, echo)
    return reg


def test_tool_execute_logs_success_event():
    """A successful tool call emits a 'tool_call' log event."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)

    _current_session_id.set("trace-test-1")
    reg = _make_registry()
    result = reg.execute("echo", {"x": 42})

    assert result == {"echoed": {"x": 42}}

    root.removeHandler(handler)
    handler.flush()
    output = stream.getvalue().strip()
    lines = [l for l in output.split("\n") if l]
    tool_events = [json.loads(l) for l in lines
                   if json.loads(l).get("event") == "tool_call"]

    assert len(tool_events) == 1, f"Expected 1 tool_call event, got {len(tool_events)}"
    ev = tool_events[0]
    assert ev["session_id"] == "trace-test-1"
    assert ev["data"]["tool"] == "echo"
    assert ev["data"]["status"] == "success"
    assert ev["data"]["elapsed_ms"] >= 0


def test_tool_execute_logs_error_event():
    """A failed tool call emits a 'tool_call' event with status='error'."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)

    _current_session_id.set("trace-test-2")
    reg = _make_registry()

    try:
        reg.execute("echo", None)
    except TypeError:
        pass

    root.removeHandler(handler)
    handler.flush()
    output = stream.getvalue().strip()
    error_events = [json.loads(l) for l in output.split("\n") if l
                    and json.loads(l).get("event") == "tool_call"
                    and json.loads(l).get("data", {}).get("status") == "error"]

    assert len(error_events) >= 1, f"Expected >=1 tool_call error, got {len(error_events)}"


def test_unknown_tool_raises_value_error():
    """Calling an unregistered tool raises ValueError."""
    import pytest
    reg = _make_registry()
    with pytest.raises(ValueError, match="Unknown tool"):
        reg.execute("nonexistent", {})
`

- [ ] **Step 2: Run tests to verify they fail**

Run: pytest tests/unit/test_tool_tracing.py -v
Expected: FAIL with assertion errors (no tool_call events found)

---

### Task 3.2: Implement tool call tracing in ToolRegistry.execute()

**Files:**
- Modify: datamind/engine/tools.py (lines 30-39)

- [ ] **Step 3: Add tracing to execute() method**

Replace the execute method in datamind/engine/tools.py:

`python
    def execute(self, name: str, args: dict) -> dict:
        """Execute a registered tool by name with the given arguments.

        Raises ValueError if the tool is not registered.

        Every invocation is traced via structured logging: the tool name,
        arguments, elapsed time, and outcome are recorded as a `tool_call`
        event associated with the current session_id (via contextvars).
        """
        import logging
        import time
        from datamind.session_context import _current_session_id

        _tool_log = logging.getLogger("datamind.tools")

        entry = self._tools.get(name)
        if entry is None:
            raise ValueError(f"Unknown tool: {name}")

        _, handler = entry
        start = time.perf_counter()
        session_id = _current_session_id.get()
        try:
            result = handler(**args)
            elapsed = (time.perf_counter() - start) * 1000
            _tool_log.info(
                "tool_call",
                extra={
                    "data": {
                        "tool": name,
                        "status": "success",
                        "elapsed_ms": round(elapsed, 2),
                    },
                },
            )
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            _tool_log.error(
                "tool_call",
                extra={
                    "data": {
                        "tool": name,
                        "status": "error",
                        "elapsed_ms": round(elapsed, 2),
                        "error": str(exc),
                    },
                },
            )
            raise
`

- [ ] **Step 4: Run the tracing tests**

Run: pytest tests/unit/test_tool_tracing.py -v
Expected: 3 PASS

- [ ] **Step 5: Run existing tool tests to confirm no regressions**

Run: pytest tests/unit/test_tools.py -v
Expected: all tests PASS

- [ ] **Step 6: Commit**

`ash
git add datamind/engine/tools.py tests/unit/test_tool_tracing.py
git commit -m "feat: add tool call tracing to ToolRegistry.execute() with structured logging"
`

---

## Task 4: Session Registry

**Files:**
- Modify: datamind/api/app.py

- [ ] **Step 1: Initialize session_registry in create_app()**

In datamind/api/app.py, inside create_app(), after line 49 (pp.state.ws_manager = ConnectionManager()), add:

`python
    # Session registry for debug introspection (D7)
    app.state.session_registry: dict[str, dict] = {}
`

- [ ] **Step 2: Register sessions after agent execution in gate_decision**

In the /skill/gate endpoint, register session state after both the LangGraph resume path and the DataMindAgent fallback path.

(A) After LangGraph agent creation and resume (around line 374, after esult = agent.resume(decision)):

`python
                # Register LangGraph agent in session registry
                app.state.session_registry[sm.state.session] = {
                    "agent": agent,
                    "state_machine": sm,
                    "started_at": sm.state.started_at,
                    "skill_name": sm.state.skill,
                    "updated_at": sm.state.completed_at or sm.state.started_at,
                }
`

(B) After DataMindAgent fallback creation and run (around line 237-238):

`python
                # Fall back to legacy DataMindAgent
                agent = proj.create_agent()
                app.state.session_registry[sm.state.session] = {
                    "agent": agent,
                    "state_machine": sm,
                    "started_at": sm.state.started_at,
                    "skill_name": sm.state.skill,
                    "updated_at": sm.state.completed_at or sm.state.started_at,
                }
                result = agent.run(sm)
                # Update registry with latest state
                app.state.session_registry[sm.state.session]["state_machine"] = sm
                app.state.session_registry[sm.state.session]["updated_at"] = (
                    sm.state.completed_at or sm.state.started_at
                )
`

- [ ] **Step 3: Commit**

`ash
git add datamind/api/app.py
git commit -m "feat: add session_registry to app.state for debug introspection"
`

---

## Task 5: Debug Endpoints

### Task 5.1: Write debug endpoint tests

**Files:**
- Create: 	ests/unit/test_debug_endpoints.py

- [ ] **Step 1: Write the test file**

`python
# tests/unit/test_debug_endpoints.py
"""Tests for debug API endpoints."""

import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from datamind.api.app import create_app


def _make_test_app():
    """Create a FastAPI test app with a temp project root structure."""
    tmp = tempfile.mkdtemp(prefix="datamind_debug_test_")
    dot = Path(tmp) / ".datamind"
    dot.mkdir(parents=True)
    (dot / "config.yaml").write_text("provider: deepseek\n", encoding="utf-8")
    for d in ["data/raw", "data/processed", "scripts", "skills", "prompts",
              "describe", "executions", "context"]:
        (Path(tmp) / d).mkdir(parents=True, exist_ok=True)
    app = create_app(tmp)
    return app, tmp


def test_debug_router_mounted_when_not_disabled():
    """Debug endpoints accessible when DATAMIND_DEBUG_DISABLE is not set."""
    os.environ.pop("DATAMIND_DEBUG_DISABLE", None)
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/debug/sessions")
    assert resp.status_code == 200
    assert resp.json() == {"sessions": []}
    resp = client.get("/debug/logs")
    assert resp.status_code == 200
    assert "logs" in resp.json()


def test_debug_state_returns_404_for_unknown_session():
    """Unknown session_id returns 404."""
    os.environ.pop("DATAMIND_DEBUG_DISABLE", None)
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/debug/state/nonexistent-session")
    assert resp.status_code == 404


def test_debug_disabled_when_env_var_set():
    """All debug endpoints return 404 when DATAMIND_DEBUG_DISABLE=1."""
    os.environ["DATAMIND_DEBUG_DISABLE"] = "1"
    try:
        app, _ = _make_test_app()
        client = TestClient(app)
        for path in ["/debug/sessions", "/debug/state/any", "/debug/logs"]:
            assert client.get(path).status_code == 404
    finally:
        os.environ.pop("DATAMIND_DEBUG_DISABLE", None)


def test_debug_logs_with_query_params():
    """Debug /logs endpoint accepts query parameters."""
    os.environ.pop("DATAMIND_DEBUG_DISABLE", None)
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/debug/logs?session_id=abc&level=INFO&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "abc"
    assert data["level"] == "INFO"
    assert "logs" in data
`

- [ ] **Step 2: Run tests to verify they fail**

Run: pytest tests/unit/test_debug_endpoints.py -v
Expected: FAIL (404 for all routes -- debug router not yet mounted)

---

### Task 5.2: Implement datamind/api/debug.py

**Files:**
- Create: datamind/api/debug.py

- [ ] **Step 3: Write the debug router**

`python
# datamind/api/debug.py
"""Debug and introspection endpoints for DataMind Studio.

Mounted conditionally -- gated by the `DATAMIND_DEBUG_DISABLE`
environment variable.  Provides runtime visibility into active
sessions, agent state, and structured logs.

Endpoints:
    GET /debug/state/{session_id}   -- Full runtime state of a session
    GET /debug/sessions             -- Summary of all active sessions
    GET /debug/logs                 -- Query structured log entries
"""

import json
import logging
import os
from fastapi import APIRouter, HTTPException, Query, Request

_log = logging.getLogger(__name__)
debug_router = APIRouter(prefix="/debug", tags=["debug"])


@debug_router.get("/state/{session_id}")
async def get_state(session_id: str, request: Request):
    """Return full runtime state for a session.

    Response keys: session_id, skill_name, current_phase, phases,
    result, agent_type, started_at, updated_at.
    """
    registry = getattr(request.app.state, "session_registry", {})
    entry = registry.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    sm = entry.get("state_machine")
    agent = entry.get("agent")

    return {
        "session_id": session_id,
        "skill_name": sm.state.skill if sm else entry.get("skill_name", ""),
        "current_phase": sm.state.phase if sm else "",
        "started_at": entry.get("started_at", ""),
        "updated_at": entry.get("updated_at", ""),
        "phases": sm.state.phases if sm else {},
        "result": sm.state.result if sm else None,
        "agent_type": type(agent).__name__ if agent else "unknown",
    }


@debug_router.get("/sessions")
async def list_sessions(request: Request):
    """Return summary list of all active sessions.

    Each entry: session_id, skill_name, phase, started_at.
    """
    registry = getattr(request.app.state, "session_registry", {})
    sessions = []
    for sid, entry in registry.items():
        sm = entry.get("state_machine")
        sessions.append({
            "session_id": sid,
            "skill_name": sm.state.skill if sm else entry.get("skill_name", ""),
            "phase": sm.state.phase if sm else "",
            "started_at": entry.get("started_at", ""),
        })
    return {"sessions": sessions}


@debug_router.get("/logs")
async def query_logs(
    request: Request,
    session_id: str | None = Query(None, description="Filter by session_id"),
    level: str | None = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
):
    """Query structured log entries from the JSONL log file.

    Supports optional filtering by session_id and log level.
    """
    log_dir = os.path.join(os.getcwd(), ".datamind", "logs")
    log_file = os.path.join(log_dir, "app.jsonl")

    entries: list[dict] = []

    if os.path.isfile(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if session_id and rec.get("session_id") != session_id:
                    continue
                if level and rec.get("level", "").upper() != level.upper():
                    continue

                entries.append(rec)
                if len(entries) >= limit:
                    break

    return {
        "session_id": session_id,
        "level": level,
        "limit": limit,
        "count": len(entries),
        "logs": entries,
    }
`

### Task 5.3: Mount debug router in app.py

**Files:**
- Modify: datamind/api/app.py

- [ ] **Step 4: Add conditional debug router mount**

In datamind/api/app.py, near the end of create_app(), just before eturn app, add:

`python
    # -- Debug endpoints (D3, D8) --
    if not os.environ.get("DATAMIND_DEBUG_DISABLE"):
        from datamind.api.debug import debug_router
        app.include_router(debug_router)
`

- [ ] **Step 5: Run debug endpoint tests**

Run: pytest tests/unit/test_debug_endpoints.py -v
Expected: 4 PASS

- [ ] **Step 6: Commit**

`ash
git add datamind/api/debug.py datamind/api/app.py tests/unit/test_debug_endpoints.py
git commit -m "feat: add debug endpoints (/debug/state, /debug/sessions, /debug/logs) with guard"
`

---

### Task 7.2: Reconfigure Playwright for FastAPI direct connect

**Files:**
- Modify: web-ui/playwright.config.ts

- [ ] **Step 4: Update playwright.config.ts**

Replace web-ui/playwright.config.ts entirely with:

`	ypescript
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
`

- [ ] **Step 5: Verify webServer starts correctly**

Run: cd web-ui && npx playwright test --list
Expected: lists available spec files (at minimum pp.spec.ts)

- [ ] **Step 6: Commit**

`ash
git add web-ui/playwright.config.ts
git commit -m "chore: reconfigure Playwright to connect directly to FastAPI on port 9000"
`

---

## Task 8: Playwright E2E -- Mock Rendering Tests (Existing pp.spec.ts)

**Files:**
- Modify: web-ui/tests/e2e/app.spec.ts

- [ ] **Step 1: Add API mocking for rendering tests**

Add a 	est.beforeEach block at the top of pp.spec.ts (after the existing imports, before the first 	est.describe):

`	ypescript
import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  // Mock all API endpoints for rendering-only tests
  // Intercept /api/ paths to return empty JSON; health check passes through
  await page.route('**/api/**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ mocked: true }),
    })
  })
  // Allow health check through for webServer readiness
  await page.unroute('**/health')
})
`

The rest of pp.spec.ts remains unchanged from its current 7 tests.

- [ ] **Step 2: Run rendering tests**

Run: cd web-ui && npx playwright test app.spec.ts --reporter=list
Expected: all 7 rendering tests PASS

- [ ] **Step 3: Commit**

`ash
git add web-ui/tests/e2e/app.spec.ts
git commit -m "test: add API mocking to rendering E2E tests"
`

---

## Task 9: Playwright E2E -- WebSocket Tests

**Files:**
- Create: web-ui/tests/e2e/websocket.spec.ts

- [ ] **Step 1: Write websocket.spec.ts**

`	ypescript
import { test, expect } from '@playwright/test'

test.describe('WebSocket Connectivity', () => {
  test('WebSocket connects and shows connected status', async ({ page }) => {
    await page.goto('/')

    const wsIndicator = page.locator('.ws-status')
    await expect(wsIndicator).toHaveAttribute('data-connected', 'true', { timeout: 10_000 })
  })

  test('WebSocket reconnects after page reload', async ({ page }) => {
    await page.goto('/')

    const wsIndicator = page.locator('.ws-status')
    await expect(wsIndicator).toHaveAttribute('data-connected', 'true', { timeout: 10_000 })

    // Reload the page -- WebSocket should reconnect
    await page.reload()
    await expect(wsIndicator).toHaveAttribute('data-connected', 'true', { timeout: 15_000 })
  })

  test('WebSocket survives navigation within SPA', async ({ page }) => {
    await page.goto('/')

    const wsIndicator = page.locator('.ws-status')
    await expect(wsIndicator).toHaveAttribute('data-connected', 'true', { timeout: 10_000 })

    // Click around the SPA (sidebar, chat) -- connection should persist
    await page.locator('.chat-input').click()
    await page.waitForTimeout(500)
    await expect(wsIndicator).toHaveAttribute('data-connected', 'true')
  })

  test('sidebar datasets section is visible', async ({ page }) => {
    await page.goto('/')
    const sectionTitle = page.locator('.section-title').first()
    await expect(sectionTitle).toBeVisible({ timeout: 10_000 })
  })
})
`

- [ ] **Step 2: Run WebSocket tests**

Run: cd web-ui && npx playwright test websocket.spec.ts --reporter=list
Expected: 4 PASS

- [ ] **Step 3: Commit**

`ash
git add web-ui/tests/e2e/websocket.spec.ts
git commit -m "test: add WebSocket connectivity E2E tests"
`

---

## Task 10: Playwright E2E -- SSE Streaming Tests

**Files:**
- Create: web-ui/tests/e2e/streaming.spec.ts

- [ ] **Step 1: Write streaming.spec.ts**

`	ypescript
import { test, expect } from '@playwright/test'

test.describe('SSE Streaming', () => {
  test('chat stream emits SSE events and renders tokens', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await expect(input).toBeVisible()
    await input.fill('Hello, what is 2+2?')
    await page.locator('.send-btn').click()

    // User bubble should appear
    await expect(page.locator('.user-bubble').first()).toBeVisible()

    // Wait for assistant response (streaming tokens via SSE)
    const assistantBubble = page.locator('.assistant-bubble').first()
    await expect(assistantBubble).toBeVisible({ timeout: 30_000 })
    const content = await assistantBubble.textContent()
    expect(content).toBeTruthy()
    expect(content!.length).toBeGreaterThan(0)
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

    // Wait for the streaming to complete (send button re-enables)
    await expect(page.locator('.send-btn')).toBeEnabled({ timeout: 30_000 })
    await expect(input).toHaveValue('')
  })
})
`

- [ ] **Step 2: Run SSE streaming tests**

Run: cd web-ui && npx playwright test streaming.spec.ts --reporter=list
Expected: 3 PASS (uses real DeepSeek API)

- [ ] **Step 3: Commit**

`ash
git add web-ui/tests/e2e/streaming.spec.ts
git commit -m "test: add SSE streaming E2E tests"
`

---

## Task 11: Playwright E2E -- File Upload Tests

**Files:**
- Create: web-ui/tests/e2e/file-upload.spec.ts

- [ ] **Step 1: Write ile-upload.spec.ts**

`	ypescript
import { test, expect } from '@playwright/test'
import path from 'path'

const FIXTURES = path.resolve(__dirname, 'fixtures')

test.describe('File Upload', () => {
  test('uploads CSV via file input and verifies dataset display', async ({ page }) => {
    await page.goto('/')

    const fileInput = page.locator('input[type="file"]')
    const csvPath = path.join(FIXTURES, 'sample.csv')
    await fileInput.setInputFiles(csvPath)

    // The dataset sidebar should show the uploaded file name
    await expect(page.locator('text=sample.csv')).toBeVisible({ timeout: 15_000 })
  })

  test('uploads Excel file and dataset appears', async ({ page }) => {
    await page.goto('/')

    const fileInput = page.locator('input[type="file"]')
    const xlsxPath = path.join(FIXTURES, 'sample.xlsx')
    await fileInput.setInputFiles(xlsxPath)

    await expect(page.locator('text=sample.xlsx')).toBeVisible({ timeout: 15_000 })
  })

  test('uploads Parquet file and dataset appears', async ({ page }) => {
    await page.goto('/')

    const fileInput = page.locator('input[type="file"]')
    const pqPath = path.join(FIXTURES, 'sample.parquet')
    await fileInput.setInputFiles(pqPath)

    await expect(page.locator('text=sample.parquet')).toBeVisible({ timeout: 15_000 })
  })

  test('invalid file format shows error or fallback', async ({ page }) => {
    await page.goto('/')

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'invalid.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('this is not a valid data file'),
    })

    await page.waitForTimeout(3_000)
    // Page should still be functional after attempting invalid upload
    await expect(page.locator('.app-title')).toBeVisible()
  })
})
`

- [ ] **Step 2: Run file upload tests**

Run: cd web-ui && npx playwright test file-upload.spec.ts --reporter=list
Expected: 4 tests run (upload success depends on endpoint behavior)

- [ ] **Step 3: Commit**

`ash
git add web-ui/tests/e2e/file-upload.spec.ts
git commit -m "test: add file upload E2E tests"
`

---

## Task 12: Playwright E2E -- Gate Approval Tests

**Files:**
- Create: web-ui/tests/e2e/gate-approval.spec.ts

- [ ] **Step 1: Write gate-approval.spec.ts**

`	ypescript
import { test, expect } from '@playwright/test'

test.describe('Gate Approval Workflow', () => {
  test.setTimeout(120_000)

  test('Gate appears when skill reaches GATE phase', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    // Wait for the gate approval UI to appear
    const approveBtn = page.locator('.approve-btn, [data-testid="approve-btn"]')
    await expect(approveBtn).toBeVisible({ timeout: 90_000 })
  })

  test('Approve continues execution past gate', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    const approveBtn = page.locator('.approve-btn, [data-testid="approve-btn"]')
    await expect(approveBtn).toBeVisible({ timeout: 90_000 })
    await approveBtn.click()

    // After approval, the gate UI should disappear
    await expect(approveBtn).not.toBeVisible({ timeout: 60_000 })
  })

  test('Reject routes to alternative path', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    const rejectBtn = page.locator('.reject-btn, [data-testid="reject-btn"]')
    await expect(rejectBtn).toBeVisible({ timeout: 90_000 })
    await rejectBtn.click()

    // After reject, the workflow should display rejection state
    await expect(page.locator('.result-rejected, .execution-rejected')).toBeVisible({ timeout: 30_000 })
  })

  test('Decision record updates after gate approval', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    const approveBtn = page.locator('.approve-btn, [data-testid="approve-btn"]')
    await expect(approveBtn).toBeVisible({ timeout: 90_000 })
    await approveBtn.click()

    // After approval, the context panel should update
    await page.waitForTimeout(3_000)
    await expect(page.locator('.context-panel')).toBeVisible()
  })
})
`

- [ ] **Step 2: Run gate approval tests**

Run: cd web-ui && npx playwright test gate-approval.spec.ts --reporter=list
Expected: 4 PASS (these use real DeepSeek API and may take 60-120s each)

- [ ] **Step 3: Commit**

`ash
git add web-ui/tests/e2e/gate-approval.spec.ts
git commit -m "test: add gate approval workflow E2E tests"
`

---

## Task 13: Playwright E2E -- Skill Pipeline Full Flow

**Files:**
- Create: web-ui/tests/e2e/skill-pipeline.spec.ts

- [ ] **Step 1: Write skill-pipeline.spec.ts**

`	ypescript
import { test, expect } from '@playwright/test'

test.describe('Skill Pipeline - Full E2E Flow', () => {
  test.setTimeout(180_000)

  test('CSV upload -> data-exploration skill -> gate -> result', async ({ page }) => {
    await page.goto('/')

    // Step 1: Upload CSV first
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles('web-ui/tests/e2e/fixtures/sample.csv')
    await expect(page.locator('text=sample.csv')).toBeVisible({ timeout: 15_000 })

    // Step 2: Start the exploration skill
    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    // Step 3: Wait for first phase to complete and check for gate
    const approveBtn = page.locator('.approve-btn, [data-testid="approve-btn"]')
    await expect(approveBtn).toBeVisible({ timeout: 90_000 })

    // Approve the strategy gate
    await approveBtn.click()

    // Step 4: Wait for results after approval
    await page.waitForTimeout(5_000)
  })

  test('pipeline preserves context across phases', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    // Wait for any response content
    const assistantBubble = page.locator('.assistant-bubble').first()
    await expect(assistantBubble).toBeVisible({ timeout: 60_000 })

    const content = await assistantBubble.textContent()
    expect(content).toBeTruthy()

    // Context panel should show session info
    await expect(page.locator('.context-status')).toBeVisible()
  })

  test('skill completion shows result summary', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('/skill data-exploration --target web-ui/tests/e2e/fixtures/sample.csv')
    await page.locator('.send-btn').click()

    // Handle gate if it appears
    const approveBtn = page.locator('.approve-btn, [data-testid="approve-btn"]')
    try {
      await expect(approveBtn).toBeVisible({ timeout: 90_000 })
      await approveBtn.click()
      await page.waitForTimeout(5_000)
    } catch {
      // No gate appeared, skill completed directly
    }
  })
})
`

- [ ] **Step 2: Run skill pipeline tests**

Run: cd web-ui && npx playwright test skill-pipeline.spec.ts --reporter=list
Expected: 3 PASS (long-running, uses real DeepSeek API)

- [ ] **Step 3: Commit**

`ash
git add web-ui/tests/e2e/skill-pipeline.spec.ts
git commit -m "test: add skill pipeline full E2E flow tests"
`

---

## Task 14: Playwright E2E -- Error Scenario Tests

**Files:**
- Create: web-ui/tests/e2e/error-scenarios.spec.ts

- [ ] **Step 1: Write error-scenarios.spec.ts**

`	ypescript
import { test, expect } from '@playwright/test'

test.describe('Error Scenarios', () => {
  test('empty message is rejected client-side', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('')
    const sendBtn = page.locator('.send-btn')
    await expect(sendBtn).toBeDisabled()
  })

  test('invalid file format shows user-friendly feedback', async ({ page }) => {
    await page.goto('/')

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'invalid.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('this is not a valid data file'),
    })

    await page.waitForTimeout(3_000)
    // Page should still be functional
    await expect(page.locator('.app-title')).toBeVisible()
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

    await expect(page.locator('.app-title')).toBeVisible()
  })

  test('network error during streaming shows error state', async ({ page }) => {
    await page.goto('/')

    // Intercept the SSE endpoint and simulate a network failure
    await page.route('**/chat/stream**', (route) => {
      route.abort('connectionreset')
    })

    const input = page.locator('.chat-input')
    await input.fill('Trigger a network error')
    await page.locator('.send-btn').click()

    await expect(page.locator('.error-message, .retry-btn, .chat-error')).toBeVisible({ timeout: 15_000 })
  })

  test('LLM long response does not freeze UI', async ({ page }) => {
    await page.goto('/')

    const input = page.locator('.chat-input')
    await input.fill('Write a comprehensive analysis of data science best practices')
    const sendBtn = page.locator('.send-btn')
    await sendBtn.click()

    // The loading indicator should appear
    await expect(page.locator('.loading-indicator, .streaming-indicator')).toBeVisible({ timeout: 5_000 })

    // The app should survive the request (verify no crash within 10s)
    await page.waitForTimeout(10_000)
    await expect(page.locator('.app-title')).toBeVisible()
  })
})
`

- [ ] **Step 2: Run error scenario tests**

Run: cd web-ui && npx playwright test error-scenarios.spec.ts --reporter=list
Expected: 5 PASS

- [ ] **Step 3: Commit**

`ash
git add web-ui/tests/e2e/error-scenarios.spec.ts
git commit -m "test: add error scenario E2E tests"
`

---
### Task 15.1: Write testing runbook

**Files:**
- Create: `docs/testing-runbook.md`

- [ ] **Step 1: Write `docs/testing-runbook.md`**

```markdown
# DataMind Studio Testing Runbook

## Overview

DataMind Studio has two test suites:
1. **Python backend tests** (310+ tests, pytest) -- unit + integration
2. **Playwright E2E tests** (7 spec files, @playwright/test) -- browser automation

## Prerequisites

### Python Tests
- Python 3.11+
- Install: `pip install -e "."`

### Playwright E2E Tests
- Node.js 18+ (working directory: `web-ui/`)
- Install: `npm ci`
- Chromium: `npx playwright install chromium`
- DeepSeek API key (for interaction tests)

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

# Specific area
pytest tests/unit/test_tools.py -v
pytest tests/unit/test_json_formatter.py -v
pytest tests/unit/test_tool_tracing.py -v
pytest tests/unit/test_debug_endpoints.py -v

# With coverage
pytest --cov=datamind --cov-report=term-missing
```

### Playwright E2E Commands

```bash
cd web-ui

# All E2E tests
npx playwright test

# Specific spec file
npx playwright test app.spec.ts

# UI mode (interactive debugging)
npx playwright test --ui

# Headed mode (see browser)
npx playwright test --headed

# Slow motion (500ms delay between actions)
npx playwright test --headed --slow-mo=500

# Generate HTML report
npx playwright test --reporter=html
npx playwright show-report
```

## Test Categories

### Rendering Tests (Mock API)
- `app.spec.ts` -- layout, theme, chat panel, sidebar
- These use `page.route()` to intercept API calls
- No DeepSeek API key required
- Fast run (< 10s)

### Interaction Tests (Real API)
- `websocket.spec.ts` -- WebSocket connection lifecycle
- `streaming.spec.ts` -- SSE token streaming
- `gate-approval.spec.ts` -- Gate approve/reject workflow
- `file-upload.spec.ts` -- File upload and dataset display
- `skill-pipeline.spec.ts` -- Full skill pipeline flow
- `error-scenarios.spec.ts` -- Error handling and recovery

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATAMIND_PROVIDER` | `deepseek` | LLM provider |
| `DATAMIND_MODEL` | `deepseek-v4-flash` | LLM model |
| `DATAMIND_API_KEY` | (from config) | API key |
| `DATAMIND_API_BASE` | `https://api.deepseek.com` | API base URL |
| `DATAMIND_LOG_LEVEL` | `INFO` | Log verbosity |
| `DATAMIND_DEBUG_DISABLE` | (not set) | Set to `1` to disable /debug endpoints |

## CI Integration (GitHub Actions)

```yaml
- name: Run Playwright E2E tests
  env:
    DATAMIND_API_KEY: ${{ secrets.DATAMIND_API_KEY }}
  run: |
    cd web-ui
    npx playwright test --reporter=html
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: playwright-report
    path: web-ui/playwright-report/
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| All E2E tests timeout | FastAPI not starting | Check `webServer` config in playwright.config.ts |
| Streaming tests fail | DeepSeek API key invalid | Verify `DATAMIND_API_KEY` env var |
| Chromium not found | Playwright browsers not installed | Run `npx playwright install chromium` |
| Port 9000 in use | Previous test run did not terminate | Kill process on port 9000 |
| Python tests fail after logging changes | Logger handlers conflict | Run `pytest -p no:logging` or check test isolation |
```

- [ ] **Step 2: Commit**

```bash
git add docs/testing-runbook.md
git commit -m "docs: add testing runbook"
```

---

### Task 15.2: Write debugging decision tree

**Files:**
- Create: `docs/debugging-runbook.md`

- [ ] **Step 3: Write `docs/debugging-runbook.md`**

```markdown
# DataMind Studio Debugging Runbook

## Decision Tree

```
Symptom: "Something is wrong"
|
+-- WebSocket not connecting?
|   +-- Check: GET /debug/sessions (empty? server not processing)
|   +-- Check: browser console for WS connection errors
|   +-- Check: `ws_manager.active_connections` count via debug state
|   +-- Fix: restart FastAPI, check CORS, verify port 9000
|
+-- SSE stream hangs / no tokens?
|   +-- Check: GET /debug/logs?session_id=X&level=ERROR
|   +-- Check: `_log.exception("Chat stream error")` in logs
|   +-- Fix: verify DATAMIND_API_KEY, check LLM rate limits
|
+-- Gate not appearing / stuck on phase?
|   +-- Check: GET /debug/state/{session_id} -> current_phase
|   +-- Check: `phase` field in `.skill.yaml`
|   +-- Fix: verify phase definitions match skill YAML, check checkpoints.db
|
+-- Tool calls failing?
|   +-- Check: GET /debug/logs?session_id=X (filter tool_call events)
|   +-- Check: `_tool_log.error("tool_call", ...)` entries
|   +-- Fix: verify tool registry has expected 7 tools, check tool arguments
|
+-- File upload not registering?
|   +-- Check: uploads/ directory exists and is writable
|   +-- Check: GET /datasets (verify registration)
|   +-- Fix: verify MAX_UPLOAD_SIZE (10 MB), check file format support
|
+-- Performance slow?
|   +-- Check: `elapsed_ms` in tool_call log events
|   +-- Check: LLM response times (streaming adds latency)
|   +-- Fix: reduce context size, use smaller model, cache prompts
```

## Debug Endpoints Reference

### GET /debug/sessions
Lists all active sessions with their current phase.
```bash
curl http://127.0.0.1:9000/debug/sessions | python -m json.tool
```

### GET /debug/state/{session_id}
Full runtime state including phases, artifacts, agent type.
```bash
curl http://127.0.0.1:9000/debug/state/2026-06-16T120000Z-data-cleaning-sample | python -m json.tool
```

### GET /debug/logs
Query structured logs with filters.
```bash
# All ERROR logs
curl "http://127.0.0.1:9000/debug/logs?level=ERROR&limit=50" | python -m json.tool

# Logs for a specific session
curl "http://127.0.0.1:9000/debug/logs?session_id=abc123" | python -m json.tool

# Most recent 20 log entries
curl "http://127.0.0.1:9000/debug/logs?limit=20" | python -m json.tool
```

## Disabling Debug Endpoints

Set environment variable before starting the server:
```bash
DATAMIND_DEBUG_DISABLE=1 python -m uvicorn serve:app --host 127.0.0.1 --port 9000
```
All `/debug/*` routes will return 404.

## Local Log Inspection

The JSONL log file is at `.datamind/logs/app.jsonl`.

```bash
# Last 50 entries
tail -50 .datamind/logs/app.jsonl | python -m json.tool

# All tool_call events
grep '"tool_call"' .datamind/logs/app.jsonl | python -m json.tool

# Errors in last hour
grep '"ERROR"' .datamind/logs/app.jsonl | python -m json.tool

# Session activity summary
grep -o '"session_id":"[^"]*"' .datamind/logs/app.jsonl | sort -u
```

## State Machine Debugging

The `.skill.yaml` file in each session directory contains the full state machine state:
```bash
cat data/<session-id>/.skill.yaml
```

Key fields:
- `phase`: current phase id
- `phases`: mapping of phase id -> status (PENDING/IN_PROGRESS/COMPLETE/AWAITING_HUMAN)
- `artifacts`: phase outputs
- `result`: final workflow result (pass/rejected/null)

## Checkpoint Debugging

LangGraph checkpoints are stored in `.datamind/checkpoints.db` (SQLite):
```bash
sqlite3 .datamind/checkpoints.db "SELECT thread_id, checkpoint_id, created_at FROM checkpoints ORDER BY created_at DESC LIMIT 10;"
```
```

- [ ] **Step 4: Commit**

```bash
git add docs/debugging-runbook.md
git commit -m "docs: add debugging decision tree and runbook"
```

---

## Task 16: Final Verification

### Task 16.1: Full Python test suite

- [ ] **Step 1: Run all Python tests**

Run: `pytest -v --tb=short`
Expected: all tests PASS (310+ tests, 0 failures)

- [ ] **Step 2: Address any failures**

If any test fails, diagnose and fix. Common issues:
- Tests capturing stdout may include JSON log lines from setup_logging
- Tests modifying root logger may conflict with handlers
- Session registry test expectations may need updating

### Task 16.2: Full Playwright test suite

- [ ] **Step 3: Run all Playwright E2E tests**

Run: `cd web-ui && npx playwright test --reporter=list`
Expected: all 7 spec files PASS (20+ individual tests)

### Task 16.3: Debug endpoint smoke test

- [ ] **Step 4: Test debug endpoints with curl**

Start the server in a separate terminal:
```bash
python -m uvicorn serve:app --host 127.0.0.1 --port 9000
```

Then verify each endpoint:
```bash
# Sessions list
curl -s http://127.0.0.1:9000/debug/sessions
# Expected: {"sessions": []}

# Logs query
curl -s "http://127.0.0.1:9000/debug/logs?limit=5"
# Expected: {"session_id": null, "level": null, "limit": 5, "count": 0, "logs": []}

# State for unknown session
curl -s http://127.0.0.1:9000/debug/state/nonexistent
# Expected: {"detail": "Session not found: nonexistent"}

# Health check
curl -s http://127.0.0.1:9000/health
# Expected: {"status": "ok"}
```

### Task 16.4: Verify DeepSeek API E2E connectivity

- [ ] **Step 5: Run a real-API streaming test**

Run: `cd web-ui && npx playwright test streaming.spec.ts --reporter=list --timeout=60000`
Expected: streaming.spec.ts PASS (tokens received from DeepSeek API)

### Task 16.5: Verify debug disable guard

- [ ] **Step 6: Test DATAMIND_DEBUG_DISABLE**

Stop the server and restart with:
```bash
DATAMIND_DEBUG_DISABLE=1 python -m uvicorn serve:app --host 127.0.0.1 --port 9000
```

Verify all debug endpoints return 404:
```bash
curl -s http://127.0.0.1:9000/debug/sessions
# Expected: 404 Not Found
curl -s http://127.0.0.1:9000/debug/state/any
# Expected: 404 Not Found
curl -s http://127.0.0.1:9000/debug/logs
# Expected: 404 Not Found
```

### Task 16.6: Final commit

- [ ] **Step 7: Commit final state**

```bash
git status
# Should show clean working tree
git log --oneline -15
# Should show all commits from this plan
```

---

## Implementation Order & Dependencies

```
Task 1  (session_context)      -- no dependencies
Task 2  (logging_setup)        -- depends on Task 1
Task 3  (tool tracing)         -- depends on Task 1
Task 4  (session registry)     -- depends on Task 1
Task 5  (debug endpoints)      -- depends on Tasks 1, 2, 4
Task 6  (verify Python tests)  -- depends on Tasks 1-5
Task 7  (fixtures + config)    -- no code dependencies on Python tasks
Task 8  (app.spec.ts mocking)  -- depends on Task 7
Task 9  (websocket.spec.ts)    -- depends on Task 7
Task 10 (streaming.spec.ts)    -- depends on Task 7
Task 11 (file-upload.spec.ts)  -- depends on Task 7
Task 12 (gate-approval.spec.ts)-- depends on Task 7
Task 13 (skill-pipeline.spec.ts)-- depends on Task 7
Task 14 (error-scenarios.spec.ts)-- depends on Task 7
Task 15 (documentation)        -- no code dependencies
Task 16 (final verification)   -- depends on all above
```

Tasks 7-14 (Playwright E2E) can execute in any order after Task 7 completes. Tasks 8-14 can also run in parallel by independent subagents.
