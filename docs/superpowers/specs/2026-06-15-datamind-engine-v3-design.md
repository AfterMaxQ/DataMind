---
comet_change: datamind-engine-v3
role: technical-design
canonical_spec: openspec
---

# DataMind Engine v3 — Technical Design

## Context

v2 established a custom agent loop (`engine/agent.py`, ~120 lines) that drives skills through AUTO/GATE phases linearly. The loop is a simple while-loop: assemble context → render prompt → call LLM → execute tools (stubs) → record decisions → advance phase. It cannot branch, execute in parallel, or map-reduce.

v2 has no real tool implementations. `_get_tool_defs()` returns `[]` and `_tool_executor` is an optional callable that nobody passes. The `web-ui` spec exists but has no implementation.

v3 completes the picture: LangGraph for complex workflows, real tools for actual data work, and a Vue 3 SPA for the user interface. DeepSeek V4 Flash is integrated as a verified OpenAI-compatible provider.

## Goals / Non-Goals

**Goals:**
- Replace the custom agent loop with LangGraph state graphs supporting conditional branching, parallel execution, map-reduce, and checkpoint/resume
- Implement a real tool system: data I/O (CSV, Parquet, Excel), auto-describe, script generation with subprocess sandbox
- Build Vue 3 Web UI: three-panel layout, drag-drop upload, chat with /skill support, WebSocket real-time updates, Dark mode
- Migrate all 7 skills to LangGraph state graphs
- Verify DeepSeek V4 Flash as a working OpenAI-compatible provider
- All 185 existing tests continue passing

**Non-Goals:**
- RAG / vector retrieval / embeddings
- Multi-agent collaboration
- Data visualization dashboard, notebook export, report generation, pipeline scheduling, data versioning, model registry (v4)
- LangGraph Server or Cloud (local execution only)

## Architecture

```
                         ┌──────────────────────────┐
                         │       Web UI              │
                         │   Vue 3 + Element Plus    │
                         │   /ws (WebSocket)         │
                         │   /chat/stream (SSE)      │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │ SSE (token)     │ WS (events+cmd) │
                    └─────────────────┼─────────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │   FastAPI (api/app.py)    │
                         │   REST + WS + SSE         │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │   DataMindAgent           │
                         │   (thin wrapper)          │
                         │   run() / approve_gate()  │
                         └────────────┬─────────────┘
                                      │ delegates
                         ┌────────────▼─────────────┐
                         │   LangGraphAgent          │
                         │   ┌─────────────────────┐ │
                         │   │ SkillGraphBuilder   │ │
                         │   │ StateGraph per skill│ │
                         │   └─────────────────────┘ │
                         │   ┌─────────────────────┐ │
                         │   │ SqliteSaver         │ │
                         │   │ checkpoints.db      │ │
                         │   └─────────────────────┘ │
                         └──────────┬───┬───────────┘
                                    │   │
              ┌─────────────────────┘   └───────────────────┐
              ▼                                             ▼
    ┌─────────────────┐                           ┌─────────────────┐
    │ engine/llm.py   │                           │ engine/tools.py │
    │ OpenAIClient    │                           │ ToolRegistry    │
    │ OllamaClient    │                           │ read_csv        │
    │ DeepSeek ✓      │                           │ execute_script  │
    └─────────────────┘                           └─────────────────┘
```

## Decisions

### D1: LangGraph State Graph — Mixed Node Granularity

Simple linear skills use a strict one-node-per-phase graph. Complex skills (with parallel execution or conditional routing) use LangGraph`s `Send` API and conditional edges.

**Detection logic in `SkillGraphBuilder`:**
- If SKILL.md YAML frontmatter has `parallel` or `routing` keys → complex graph construction
- Otherwise → linear graph with sequential edges

**State schema:**
```python
class SkillState(TypedDict):
    session_id: str
    skill_name: str
    target: str
    current_phase: str
    phase_results: dict[str, dict]  # phase_id → {status, output, artifacts}
    messages: list[dict]            # conversation history for LLM
    tool_calls: list[dict]          # accumulated tool calls
    gate_decision: dict | None      # human decision at GATE
    result: str | None              # final result
```

### D2: SKILL.md Extension — YAML Frontmatter

Backward-compatible extension. Existing skills without frontmatter default to linear behavior. `SkillParser` already handles YAML + markdown (same pattern as prompt templates).

**Format:**
```yaml
---
skill: data-cleaning
version: 2
routing:
  gate-3: { approve: phase-4, reject: phase-2 }
tools:
  phase-1: [read_csv, describe_dataset]
  phase-4: [generate_script, execute_script]
parallel: false
---
# Data Cleaning
**Purpose:** Clean raw data...
## Workflow
1. **Analyze** (AUTO) — ...
```

**Parallel skill example (model-training):**
```yaml
parallel:
  phase-4: { candidates: 3, merge: phase-5 }
```

### D3: Checkpoint Strategy — SqliteSaver + .skill.yaml

LangGraph`s `SqliteSaver` handles checkpoint/resume within a skill session. `.skill.yaml` remains as a lightweight human-readable summary. SqliteSaver is synchronous; writes run via `run_in_executor` to avoid blocking the FastAPI event loop.

```
.datamind/skill-sessions/2026-06-15-sales-cleaning/
├── .skill.yaml          # summary: phase, status, result (~200 bytes)
├── checkpoints.db       # LangGraph SqliteSaver (full graph state)
├── phase-1-analyze.md   # Analysis output
├── ...
```

### D4: Agent Layer — Thin Wrapper

`engine/langgraph_agent.py` contains `SkillGraphBuilder` and `LangGraphAgent`. `engine/agent.py`'s `DataMindAgent` is rewritten as a thin compatibility wrapper preserving the public API (`run()`, `approve_gate()`, event types).

```
                    ┌──────────────────────┐
                    │   DataMindAgent       │  ← thin wrapper (preserved API)
                    │   run() / approve()   │
                    └──────────┬───────────┘
                               │ delegates
                    ┌──────────▼───────────┐
                    │   LangGraphAgent      │  ← new engine
                    │   SkillGraphBuilder   │
                    │   SqliteSaver         │
                    └──────────────────────┘
```

### D5: Tool System — ToolRegistry + Sandbox

`ToolRegistry` in `engine/tools.py` stores `(schema, callable)` pairs. Tools are registered at startup. `get_definitions()` returns OpenAI-compatible tool schemas for LLM injection. `execute(name, args)` dispatches to the registered callable.

**Minimum viable tools:**

| Tool | Function |
|------|----------|
| `read_csv` | Read CSV with auto-detect encoding, return schema + sample |
| `read_parquet` | Read Parquet, return schema + sample |
| `read_excel` | Read Excel (openpyxl), return schema + sample |
| `describe_dataset` | Run auto-describe via existing `DescribeEngine` |
| `generate_script` | Generate Python script from template + parameters |
| `execute_script` | Run Python script in subprocess sandbox with timeout |
| `list_files` | List files in a directory |

**Sandbox:** Scripts execute via `subprocess.run()` inside a `tempfile.TemporaryDirectory` to limit filesystem side effects. Timeout (300s default) and output size limit (1MB). Trusted user model — not full multi-tenant isolation.

### D6: Web UI — Vue 3 + Element Plus

Standalone Vue 3 project in `web-ui/` built with Vite. Element Plus for layout, forms, dialogs, upload, and built-in dark mode. Dual-channel communication: SSE for token streaming, WebSocket for real-time events and commands.

**Project structure:**
```
web-ui/
├── src/
│   ├── components/
│   │   ├── DataSidebar.vue      # left panel
│   │   ├── ChatPanel.vue        # center panel
│   │   ├── ContextPanel.vue     # right panel
│   │   ├── LineageGraph.vue     # D3.js lineage viz
│   │   ├── GateApproval.vue     # approval button component
│   │   └── CodeBlock.vue        # syntax-highlighted code
│   ├── composables/
│   │   ├── useWebSocket.ts      # WebSocket connection management
│   │   ├── useChat.ts           # chat state + SSE streaming
│   │   └── useTheme.ts          # dark/light mode
│   ├── stores/
│   │   └── session.ts           # Pinia store
│   ├── App.vue
│   └── main.ts
├── index.html
├── vite.config.ts
└── package.json
```

**WebSocket protocol:**
- Server → Client: `lineage_update`, `decision_update`, `phase_transition`, `token_stream`
- Client → Server: `chat_message`, `skill_invoke`, `gate_decision`

**Development:** Vite dev server proxies `/ws`, `/api`, `/chat` to FastAPI (`localhost:8000`).
**Production:** FastAPI serves built static files from `web-ui/dist/`.

### D7: DeepSeek Integration — Zero Code Change

DeepSeek`s API is OpenAI-compatible. No code changes to `engine/llm.py`. Config template includes DeepSeek as a pre-configured provider. Dedicated integration test verifies chat, streaming, and tool calling.

**Config template:**
```yaml
llm:
  providers:
    deepseek:
      api_base: "https://api.deepseek.com"
      api_key: "${DEEPSEEK_API_KEY}"
      models:
        - deepseek-v4-flash
    openai:
      api_base: "https://api.openai.com/v1"
      api_key: "${OPENAI_API_KEY}"
      models:
        - gpt-4o
    ollama:
      api_base: "http://localhost:11434/v1"
      models: auto
```

### D8: Skill Migration Order

Simple to complex, one commit per skill:

1. `auto-archive` — 5 phases, purely linear (simplest)
2. `requirement-discussion` — 7 phases, linear with multiple gates
3. `report-generation` — 6 phases, linear
4. `data-exploration` — 5 phases, linear
5. `data-cleaning` — 7 phases, linear with gate routing
6. `feature-engineering` — 8 phases, linear with gate routing
7. `model-training` — 7 phases, **parallel execution + conditional gate routing** (most complex)

## Module Specifications

### New Modules

**`engine/langgraph_agent.py`**
- `SkillState(TypedDict)` — graph state schema
- `SkillGraphBuilder` — constructs `StateGraph` from SKILL.md + YAML frontmatter
  - `from_skill_definition(skill_def, tool_registry) → StateGraph`
  - Auto-detects linear vs complex (parallel/conditional) graph structure
- `LangGraphAgent` — graph execution engine
  - `run(session, user_input) → AgentEvent`
  - `resume(decision) → AgentEvent`
  - Integrates `SqliteSaver` for checkpointing
  - Updates `.skill.yaml` on every state transition

**`engine/tools.py`**
- `ToolRegistry` — registry with `register(name, schema, callable)`, `get_definitions()`, `execute(name, args)`
- `read_csv(path, nrows=10) → dict` — CSV reader with encoding auto-detect
- `read_parquet(path, nrows=10) → dict` — Parquet reader
- `read_excel(path, nrows=10) → dict` — Excel reader (openpyxl)
- `describe_dataset(path) → dict` — Auto-describe via `DescribeEngine`
- `generate_script(template, params, output_path) → dict` — Script generation
- `execute_script(path, timeout=300) → dict` — Subprocess sandbox execution
- `list_files(directory) → dict` — Directory listing

**`web-ui/`** — Vue 3 + Vite + TypeScript + Element Plus + Pinia
- 6 components, 3 composables, 1 Pinia store
- Dev proxy to FastAPI, prod static serving

### Modified Modules

**`engine/agent.py`** — Rewrite
- `DataMindAgent` becomes thin wrapper delegating to `LangGraphAgent`
- Preserves `run()`, `approve_gate()`, `AgentResponse`, `WaitForApproval`, `AgentError`, `SkillComplete`
- Removes `_get_tool_defs()`, `_tool_executor`, `_continue()`, `_process_auto_phase()`

**`engine/skills.py`** — Extend
- `SkillParser` extended to parse YAML frontmatter (routing, tools, parallel)
- `SkillService` extended to pass tool registry to agent

**`api/app.py`** — Extend
- Add `GET /ws` — WebSocket upgrade endpoint with connection manager
- Add `POST /upload` — file upload for drag-drop
- Update `POST /skill/gate` — delegate to `LangGraphAgent.resume()`
- WebSocket broadcast on phase transitions (hooked into `LangGraphAgent`)

**`engine/skill_state.py`** — Extend
- Add checkpoint integration: sync `.skill.yaml` writes with LangGraph state transitions

**`datamind/config.py`** — Extend
- LLM config template includes DeepSeek provider entry

## Testing Strategy

**Per module (TDD):**
- Tool system: RED → GREEN per tool, ToolRegistry integration test
- LangGraph agent: graph structure verification, state transitions, interrupt/resume cycle
- Agent wrapper: existing `DataMindAgent` tests pass through wrapper unchanged


- API: WebSocket lifecycle, upload, gate approval through LangGraph

**Per skill migration:**
- Integration test: full LangGraph execution with mock LLM, verify graph structure and routing

**Provider integration:**
- DeepSeek: chat + streaming + tool calling against real API

**Web UI:**
- E2E (Playwright): full flow — upload CSV → chat → /skill data-cleaning → gate approve → lineage update

**Regression:**
- All 185 existing tests must pass at every migration step

## Risks / Trade-offs

- **[Risk] LangGraph API instability (<1.0)** → Pin version in pyproject.toml; all LangGraph interaction isolated to `engine/langgraph_agent.py`
- **[Risk] SqliteSaver blocking event loop** → `run_in_executor` with thread pool; checkpoint writes are <1ms
- **[Risk] Existing tests break during agent migration** → Thin wrapper preserves `DataMindAgent` API; run full test suite after each skill migration
- **[Risk] Script sandbox security** → Trusted user model (single-user desktop); `TemporaryDirectory` limits filesystem side effects; timeout + output limits as guardrails
- **[Trade-off] Dual channel (SSE + WS) vs single WebSocket** → Two connections but each is simpler; avoids reimplementing SSE semantics on WebSocket
- **[Trade-off] Element Plus bundle size** → Slightly heavier than hand-written CSS but saves weeks of component development; tree-shaking removes unused components
- **[Trade-off] LangGraph adds dependency weight** → 1 new pip dependency (`langgraph`); local `SqliteSaver` needs no server infrastructure
- **[Trade-off] Dual state (checkpoints.db + .skill.yaml)** → Slight redundancy but different purposes: machine recovery vs human readability

## Migration Plan

1. Add `langgraph` to pyproject.toml, install, verify 185 tests pass
2. Implement `engine/tools.py` (ToolRegistry + 7 tools + tests)
3. Implement `engine/langgraph_agent.py` (SkillGraphBuilder + LangGraphAgent + tests)
4. Rewrite `engine/agent.py` as thin wrapper, verify all existing agent tests pass
5. Migrate 7 skills one at a time (7 commits, 7 integration tests)
6. Add DeepSeek config template + integration test
7. Extend `api/app.py` with WebSocket, upload, updated gate endpoint
8. Scaffold `web-ui/`, implement panels sequentially, add E2E test
9. Final integration: full `/skill data-cleaning` flow through Web UI

## Open Questions

None — all resolved during design exploration.
