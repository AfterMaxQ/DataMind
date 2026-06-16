# DataMind Studio Debugging Runbook

## Decision Tree

Start here when something is wrong. Follow the branch that matches your symptom.

```
Symptom: "Something is wrong"
|
+-- WebSocket not connecting?
|   +-- Check: GET /debug/sessions (empty? server may not be processing)
|   +-- Check: browser DevTools Console for WebSocket connection errors
|   +-- Check: ws_manager.active_connections count via server logs
|   +-- Likely causes: CORS misconfiguration, port mismatch, server not running
|   +-- Fix: restart FastAPI on port 9003, verify CORS allows origins, check firewall
|
+-- SSE stream hangs / no tokens appearing?
|   +-- Check: GET /debug/logs?level=ERROR for "Chat stream error"
|   +-- Check: .datamind/logs/app.jsonl for exception tracebacks
|   +-- Check: Playwright test is using route.continue(), NOT route.fetch()+route.fulfill()
|   +-- Likely causes: API key invalid, LLM rate limited, SSE pattern wrong
|   +-- Fix: verify DATAMIND_API_KEY, check LLM rate limits, ensure route.continue() is used
|
+-- Gate not appearing / stuck on a phase?
|   +-- Check: GET /debug/state/{session_id} -> current_phase
|   +-- Check: .skill.yaml -> phase field (should show AWAITING_HUMAN for GATE phases)
|   +-- Check: .datamind/checkpoints.db -> find matching thread_id
|   +-- Likely causes: phase definition mismatch, checkpoint not saved, agent error swallowed
|   +-- Fix: verify phase definitions match skill YAML, check agent logs for errors
|
+-- Tool calls failing?
|   +-- Check: GET /debug/logs?session_id=X -> filter "tool_call" events
|   +-- Check: .datamind/logs/app.jsonl for tool_call events with status="error"
|   +-- Check: tool is registered in ToolRegistry (grep for name in tools.py)
|   +-- Likely causes: tool not registered, wrong argument signature, internal error
|   +-- Fix: verify tool registry has expected tools, check tool handler arguments
|
+-- File upload not registering?
|   +-- Check: uploads/ directory exists and is writable on the server
|   +-- Check: GET /datasets (verify the dataset was registered)
|   +-- Check: server logs for "registering dataset" or file-related errors
|   +-- Likely causes: file format not supported, file too large, path issue
|   +-- Fix: verify MAX_UPLOAD_SIZE (10 MB default), check supported file formats (CSV, XLSX, Parquet)
|
+-- Performance slow / UI freezing?
|   +-- Check: elapsed_ms in tool_call log events in .datamind/logs/app.jsonl
|   +-- Check: LLM response times (streaming adds inherent latency)
|   +-- Check: number of active sessions via GET /debug/sessions
|   +-- Likely causes: large context window, slow model, too many concurrent sessions
|   +-- Fix: reduce context size, switch to faster model, cache prompts, limit concurrent sessions
```

---

## Debug Endpoints Reference

Debug endpoints are mounted at `/debug/*` on the FastAPI server (port 9003). They are gated by the `DATAMIND_DEBUG_DISABLE` environment variable -- set it to `1` to disable all debug routes (they will return 404).

### GET /debug/sessions

Lists all active sessions with their current phase.

```bash
curl http://127.0.0.1:9003/debug/sessions | python -m json.tool
```

Response:
```json
{
  "sessions": [
    {
      "session_id": "2026-06-16T120000Z-data-cleaning-sample",
      "skill_name": "data-cleaning",
      "phase": "AWAITING_HUMAN",
      "started_at": "2026-06-16T12:00:00Z"
    }
  ]
}
```

### GET /debug/state/{session_id}

Full runtime state for a specific session, including phases, result, and agent type.

```bash
curl http://127.0.0.1:9003/debug/state/2026-06-16T120000Z-data-cleaning-sample | python -m json.tool
```

Response includes: `session_id`, `skill_name`, `current_phase`, `phases` (all phases with status), `result`, `agent_type`, `started_at`, `updated_at`.

Returns 404 if the session is not found in the registry.

### GET /debug/logs

Query structured JSONL log entries with optional filters.

```bash
# All ERROR-level logs
curl "http://127.0.0.1:9003/debug/logs?level=ERROR&limit=50" | python -m json.tool

# Logs for a specific session
curl "http://127.0.0.1:9003/debug/logs?session_id=abc123&limit=200" | python -m json.tool

# Most recent 20 log entries (any level)
curl "http://127.0.0.1:9003/debug/logs?limit=20" | python -m json.tool

# Tool call events for a session (filter client-side)
curl -s "http://127.0.0.1:9003/debug/logs?session_id=abc123&limit=500" | python -c "
import json, sys
data = json.load(sys.stdin)
for log in data['logs']:
    if log.get('event') == 'tool_call':
        print(json.dumps(log, indent=2))
"
```

Query parameters: `session_id` (string), `level` (DEBUG/INFO/WARNING/ERROR), `limit` (1-1000, default 100).

---

## Disabling Debug Endpoints

In production or when you do not want debug routes exposed, set the environment variable before starting the server:

```bash
# PowerShell
$env:DATAMIND_DEBUG_DISABLE = "1"
python -m uvicorn serve:app --host 127.0.0.1 --port 9003

# Bash
DATAMIND_DEBUG_DISABLE=1 python -m uvicorn serve:app --host 127.0.0.1 --port 9003
```

All `/debug/*` routes will return 404 Not Found when disabled.

---

## Local Log Inspection

Structured logs are written to `.datamind/logs/app.jsonl` in JSON Lines format (one JSON object per line). Each log entry contains: `ts`, `level`, `module`, `event`, `session_id`, `data`, `elapsed_ms`.

### Commands (Bash / Git Bash)

```bash
# Last 50 entries as formatted JSON
tail -50 .datamind/logs/app.jsonl | while read line; do echo "$line" | python -m json.tool; done

# All tool_call events
grep '"tool_call"' .datamind/logs/app.jsonl

# Error-level events only
grep '"level":"ERROR"' .datamind/logs/app.jsonl

# Session IDs with activity
grep -o '"session_id":"[^"]*"' .datamind/logs/app.jsonl | sort -u

# Count events by level
grep -o '"level":"[^"]*"' .datamind/logs/app.jsonl | sort | uniq -c

# Watch logs in real time (tail follows the file)
tail -f .datamind/logs/app.jsonl | grep --line-buffered '"ERROR"'
```

### Commands (PowerShell)

```powershell
# Last 50 entries
Get-Content .datamind\logs\app.jsonl -Tail 50

# All tool_call events
Select-String -Path .datamind\logs\app.jsonl -Pattern '"tool_call"'

# Error-level events only
Select-String -Path .datamind\logs\app.jsonl -Pattern '"ERROR"'
```

Log files are rotated daily (midnight) with 7 days of retention. Current file is always `app.jsonl`; older files are named `app.jsonl.YYYY-MM-DD`.

---

## State Machine Debugging

Each session stores its state machine in a `.skill.yaml` file within its session directory under `data/<session-id>/`.

```bash
cat data/2026-06-16T120000Z-data-cleaning-sample/.skill.yaml
```

Key fields to inspect:

| Field | Description |
|-------|-------------|
| `phase` | Current phase identifier (e.g., `data-loading`, `strategy`, `execution`, `report`) |
| `phases` | Map of phase id -> status: `PENDING`, `IN_PROGRESS`, `COMPLETE`, `AWAITING_HUMAN` |
| `artifacts` | Outputs produced by each phase |
| `result` | Final workflow result: `pass`, `rejected`, or `null` (not yet complete) |
| `session` | Session identifier string |
| `skill` | Skill name (e.g., `data-exploration`, `data-cleaning`) |
| `started_at` | ISO 8601 timestamp when the session started |
| `completed_at` | ISO 8601 timestamp when the session finished (null if still running) |

To find sessions on disk:

```bash
ls data/*/.skill.yaml
```

---

## Checkpoint Debugging

LangGraph checkpoints are stored in `.datamind/checkpoints.db` (SQLite). Each checkpoint captures the full agent state at a point in the workflow graph.

```bash
# List recent checkpoints
sqlite3 .datamind/checkpoints.db "SELECT thread_id, checkpoint_id, created_at FROM checkpoints ORDER BY created_at DESC LIMIT 10;"

# Find checkpoints for a specific thread
sqlite3 .datamind/checkpoints.db "SELECT * FROM checkpoints WHERE thread_id LIKE '%data-cleaning%' ORDER BY created_at DESC;"

# Count checkpoints per thread
sqlite3 .datamind/checkpoints.db "SELECT thread_id, COUNT(*) as cnt FROM checkpoints GROUP BY thread_id ORDER BY cnt DESC;"

# Schema overview
sqlite3 .datamind/checkpoints.db ".schema"
```

If a gate is not appearing when expected, check whether a checkpoint was saved at the phase boundary. Missing checkpoints often mean the agent did not reach or save state at the GATE node.

---

## Common Debugging Workflows

### Debugging a Stuck Gate Approval

1. **Identify the session**: Get the session ID from the UI or from `GET /debug/sessions`.
2. **Check runtime state**: `curl http://127.0.0.1:9003/debug/state/{session_id}` -- verify `current_phase` is what you expect.
3. **Check disk state**: `cat data/{session_id}/.skill.yaml` -- verify `phases.<current>.status` is `AWAITING_HUMAN`.
4. **Check checkpoints**: `sqlite3 .datamind/checkpoints.db "SELECT * FROM checkpoints WHERE thread_id='{session_id}' ORDER BY created_at DESC LIMIT 5;"` -- verify the agent saved a checkpoint at the gate boundary.
5. **Check logs**: `grep '"session_id":"{session_id}"' .datamind/logs/app.jsonl | grep ERROR` -- look for swallowed exceptions.

### Debugging SSE Streaming Failures

1. **Verify the route pattern**: In the Playwright test, confirm `route.continue()` is used for `/chat/stream` routes (not `route.fetch()` + `route.fulfill()`). The latter buffers the entire SSE stream and deadlocks.
2. **Check API connectivity**: `curl -s "http://127.0.0.1:9003/chat/stream?message=test"` -- should see SSE events.
3. **Check API key**: `curl http://127.0.0.1:9003/models` -- should return model list without error.
4. **Check logs for errors**: `grep '"level":"ERROR"' .datamind/logs/app.jsonl | tail -20`.

### Debugging Tool Call Failures

1. **Find the tool_call events**: `grep '"tool_call"' .datamind/logs/app.jsonl | tail -20`.
2. **Look at the error data**: Failed calls have `"status":"error"` with an `error` field in `data`.
3. **Check tool registration**: Verify the tool name appears in the ToolRegistry. Check `datamind/engine/tools.py` for `register()` calls.
4. **Check arguments**: The error message often contains the specific argument mismatch.

---

## Reference: Port Configuration

| Component | Port |
|-----------|------|
| FastAPI backend | 9003 |
| Playwright baseURL | 9003 |
| Vite dev server | 5173 (development only, proxied to 9003) |

Port 9003 was chosen because port 9000 conflicts with MinIO in the local development environment. This is configured in:
- `web-ui/playwright.config.ts` -- `webServer.command` and `baseURL`
- `web-ui/vite.config.ts` -- proxy target (if running dev mode)
