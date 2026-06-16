# datamind-engine-v3 — Design Document

## Context

v2 established a custom agent loop (`engine/agent.py`, ~120 lines) that drives skills through AUTO/GATE phases linearly. The loop is a simple while-loop: assemble context → render prompt → call LLM → execute tools (stubs) → record decisions → advance phase. It cannot branch (REJECT → back to proposal), execute nodes in parallel (train 3 models at once), or map-reduce (fan-out validation).

v2 also has no real tool implementations. `_get_tool_defs()` returns `[]` and `_tool_executor` is an optional callable that nobody passes. Skills describe workflows but can't actually read CSV files, run pandas operations, or execute scripts.

The `web-ui` spec exists in `openspec/specs/web-ui/spec.md` but has no implementation. The API has SSE streaming but no WebSocket for real-time updates.

v3 completes the picture: LangGraph for complex workflows, real tools for actual data work, and a Vue 3 SPA for the user interface.

## Goals / Non-Goals

**Goals:**
- Replace the custom agent loop with LangGraph state graphs: conditional branching, parallel execution, map-reduce, checkpoint/resume
- Implement real tools: data I/O (CSV, Parquet, Excel), auto-describe, script generation with subprocess sandbox
- Build Vue 3 Web UI: three-panel layout, drag-drop upload, chat with /skill support, context panel, WebSocket real-time updates, Dark mode
- Migrate all 7 skills to LangGraph state graphs
- Verify DeepSeek V4 Flash as a working OpenAI-compatible provider
- 185 existing tests continue passing

**Non-Goals:**
- RAG / vector retrieval / embeddings
- Multi-agent collaboration
- Data visualization dashboard (v4)
- Notebook export / report generation / pipeline scheduling / data versioning / model registry (v4)
- LangGraph Server or LangGraph Cloud (local execution only)

## Decisions

### D1: LangGraph State Graph — Single graph per skill, not one graph per phase

**Decision**: Build a `SkillGraphBuilder` that constructs one LangGraph `StateGraph` per skill definition. Each skill phase becomes a node; transitions are edges. GATE phases become `interrupt` nodes. Conditional edges handle REJECT/APPROVE routing.

**Rationale**: One graph per skill maps naturally to the skill lifecycle. LangGraph's `interrupt()` primitive is designed for human-in-the-loop—a first-class match for GATE phases. The graph structure is determined at session creation time from the skill's phase definitions.

**Alternatives considered**:
- One monolithic graph for all skills: Overly complex, harder to debug individual skills
- Keep `.skill.yaml` + add LangGraph on top: Two sources of truth for state; complexity without benefit. LangGraph's checkpointer replaces `.skill.yaml` phase tracking

**State schema**:
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

### D2: Checkpoint Strategy — LangGraph checkpointer + .skill.yaml coexistence

**Decision**: LangGraph's `SqliteSaver` handles checkpoint/resume within a skill session. `.skill.yaml` remains as a lightweight summary for discovery and API responses. The session directory structure is preserved.

**Rationale**: LangGraph checkpoints capture the full graph state (messages, tool results, phase transitions) in SQLite. `.skill.yaml` provides a human-readable summary (~200 bytes) that the API can return without loading LangGraph. Both are written on every state transition.

```
.datamind/skill-sessions/2026-06-15-sales-cleaning/
├── .skill.yaml          # summary: phase, status, result (human-readable)
├── checkpoints.db       # LangGraph SqliteSaver (full state)
├── phase-1-analyze.md   # Analysis output
├── ...
```

### D3: Agent Layer — DataMindAgent becomes a thin wrapper, LangGraphAgent is the engine

**Decision**: `engine/langgraph_agent.py` contains `SkillGraphBuilder` (graph construction) and `LangGraphAgent` (graph execution). `engine/agent.py`'s `DataMindAgent` is rewritten as a thin compatibility wrapper that delegates to `LangGraphAgent`. The public API (`run()`, `approve_gate()`) is preserved.

**Rationale**: API endpoints (`api/app.py`) and MCP server (`mcp/server.py`) call `DataMindAgent.run()` and `DataMindAgent.approve_gate()`. Rewriting those callers adds risk. A thin wrapper preserves the contract while replacing the engine.

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

### D4: Tool System — ToolRegistry + script sandbox

**Decision**: A `ToolRegistry` in `engine/tools.py` holds all available tool definitions. Each tool is a `(schema, callable)` pair. Tools are registered at startup. The `LangGraphAgent` queries `ToolRegistry.get_definitions()` to inject into LLM context, and `ToolRegistry.execute(name, args)` to run them.

**Minimum viable tool set**:
| Tool | Function |
|------|----------|
| `read_csv` | Read CSV with auto-detect encoding, return schema + sample |
| `read_parquet` | Read Parquet, return schema + sample |
| `read_excel` | Read Excel (openpyxl), return schema + sample |
| `describe_dataset` | Run auto-describe: row/col count, types, nulls, distributions |
| `generate_script` | Generate a Python script from a template + parameters |
| `execute_script` | Run a Python script in subprocess sandbox, capture stdout/stderr |
| `list_files` | List files in a directory (raw/, processed/, scripts/) |

**Sandbox**: `execute_script` runs via `subprocess.run([sys.executable, script_path], cwd=project_root, timeout=300, capture_output=True)`. Not a full security sandbox—trusted user assumption (single-user desktop app). Timeout and output size limits prevent runaway scripts.

### D5: Web UI Architecture — Vite + Vue 3 SPA, served by FastAPI

**Decision**: The Web UI is a standalone Vue 3 project in `web-ui/` built with Vite. In development, Vite dev server proxies API requests to FastAPI. In production, FastAPI serves the built static files. WebSocket for real-time updates, REST for CRUD operations.

```
web-ui/
├── src/
│   ├── components/
│   │   ├── DataSidebar.vue      # left panel
│   │   ├── ChatPanel.vue        # center panel
│   │   ├── ContextPanel.vue     # right panel
│   │   ├── LineageGraph.vue     # D3/Cytoscape lineage viz
│   │   ├── GateApproval.vue     # approval button component
│   │   └── CodeBlock.vue        # syntax-highlighted code
│   ├── composables/
│   │   ├── useWebSocket.ts      # WebSocket connection management
│   │   ├── useChat.ts           # chat state + SSE/WS
│   │   └── useTheme.ts          # dark/light mode
│   ├── stores/
│   │   └── session.ts           # Pinia store for session state
│   ├── App.vue
│   └── main.ts
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

**WebSocket protocol**:
- Server → Client events: `lineage_update`, `decision_update`, `phase_transition`, `token_stream`
- Client → Server events: `chat_message`, `skill_invoke`, `gate_decision`

**REST endpoints** (new):
- `GET /ws` — WebSocket upgrade endpoint
- `POST /upload` — file upload (drag-drop)

### D6: DeepSeek Integration — Zero code change, config + test

**Decision**: DeepSeek's API is OpenAI-compatible. No code changes needed in `engine/llm.py`. Add DeepSeek as a pre-configured provider in the config template, write a dedicated integration test, and include `deepseek-v4-flash` in the default model list.

**Config template addition**:
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
      models: auto  # ollama list
```

### D7: Skill Migration Strategy — Phased, one skill at a time

**Decision**: Migrate skills in dependency order: simplest first, complex last. Each migration: (1) define LangGraph state graph, (2) write test, (3) verify old behavior preserved. Order: `auto-archive` → `requirement-discussion` → `report-generation` → `data-exploration` → `data-cleaning` → `feature-engineering` → `model-training`.

`model-training` is last because it exercises the most complex LangGraph features: parallel model training, conditional gate routing.

## Risks / Trade-offs

- **[Risk] LangGraph learning curve** → Start with simple skills, build `SkillGraphBuilder` patterns, reuse across skills
- **[Risk] LangGraph API instability** → Pin version, LangGraph is <1.0 but widely used; any breakage isolated to `engine/langgraph_agent.py`
- **[Risk] Existing tests break during agent migration** → Thin wrapper preserves `DataMindAgent` API; run full test suite after each skill migration
- **[Risk] Script sandbox security** → Trusted user model (single-user desktop); timeout + output limits as basic guardrails, not full sandboxing
- **[Risk] Web UI development complexity** → Start with minimal viable layout (three empty panels), iterate feature-by-feature
- **[Trade-off] LangGraph adds dependency weight** → 1 new pip dependency (`langgraph`); no server infrastructure needed (local SqliteSaver)
- **[Trade-off] Dual state (checkpoints.db + .skill.yaml)** → Slight redundancy but different purposes: machine recovery vs human readability. `.skill.yaml` is ~200 bytes, negligible overhead

## Migration Plan

1. Add `langgraph` to `pyproject.toml` dependencies
2. Implement `engine/tools.py` with `ToolRegistry` and minimum viable tools
3. Implement `engine/langgraph_agent.py` with `SkillGraphBuilder` and `LangGraphAgent`
4. Rewrite `engine/agent.py` as thin wrapper delegating to `LangGraphAgent`
5. Run full test suite (must pass, 185 tests)
6. Migrate skills one at a time in dependency order (7 skills, 7 commits)
7. Add DeepSeek config template + integration test
8. Scaffold `web-ui/` Vue 3 project, implement panels sequentially
9. Add WebSocket support to `api/app.py`
10. Final integration test: full `/skill data-cleaning` flow through Web UI

## Open Questions

- None remaining — all clarified during design exploration
