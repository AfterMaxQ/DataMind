## 1. Setup and Dependencies

- [x] 1.1 Add `langgraph` to pyproject.toml dependencies
- [x] 1.2 Run `pip install -e ".[dev]"` to install langgraph
- [x] 1.3 Verify all 185 existing tests pass on current master

## 2. Tool System

- [ ] 2.1 Implement `ToolRegistry` class in `engine/tools.py` with `register()`, `get_definitions()`, `execute()` methods
- [ ] 2.2 Implement `read_csv` tool with encoding auto-detect, schema inference, and sample output
- [ ] 2.3 Implement `read_parquet` and `read_excel` tools
- [ ] 2.4 Implement `describe_dataset` tool using existing `DescribeEngine`
- [ ] 2.5 Implement `generate_script` tool with template rendering
- [ ] 2.6 Implement `execute_script` tool with subprocess sandbox (timeout, output limit)
- [ ] 2.7 Implement `list_files` tool for directory listing
- [ ] 2.8 Write unit tests for ToolRegistry and each tool
- [ ] 2.9 Write TDD test for ToolRegistry — verify RED then implement to GREEN

## 3. LangGraph Agent Engine

- [ ] 3.1 Implement `SkillState` TypedDict with all required fields
- [ ] 3.2 Implement `SkillGraphBuilder` class that constructs a `StateGraph` from skill phase definitions
- [ ] 3.3 Implement `LangGraphAgent` class with graph compilation and execution
- [ ] 3.4 Implement AUTO phase node: context assembly → prompt → LLM → tool loop → record
- [ ] 3.5 Implement GATE phase node with LangGraph `interrupt()` for pause and resume
- [ ] 3.6 Implement conditional routing: APPROVE → next phase, REJECT → fallback phase
- [ ] 3.7 Implement `SqliteSaver` checkpoint integration for `checkpoints.db`
- [ ] 3.8 Implement `.skill.yaml` coexistence (summary written on every state transition)
- [ ] 3.9 Implement parallel execution support via LangGraph `Send` API
- [ ] 3.10 Implement map-reduce fan-out validation pattern
- [ ] 3.11 Write unit tests for LangGraphAgent, SkillGraphBuilder, and state transitions
- [ ] 3.12 Write TDD test for LangGraph state graph — verify RED then implement to GREEN

## 4. Agent Wrapper Migration

- [ ] 4.1 Rewrite `DataMindAgent` in `engine/agent.py` as thin wrapper delegating to `LangGraphAgent`
- [ ] 4.2 Preserve `run()`, `approve_gate()`, `AgentResponse`, `WaitForApproval`, `AgentError`, `SkillComplete` public API
- [ ] 4.3 Remove `_get_tool_defs()` and old `_tool_executor`; replace with `ToolRegistry` delegation
- [ ] 4.4 Verify all existing agent tests pass through the wrapper

## 5. Skill Migration to LangGraph

- [ ] 5.1 Migrate `auto-archive` skill to LangGraph state graph
- [ ] 5.2 Migrate `requirement-discussion` skill to LangGraph state graph
- [ ] 5.3 Migrate `report-generation` skill to LangGraph state graph
- [ ] 5.4 Migrate `data-exploration` skill to LangGraph state graph
- [ ] 5.5 Migrate `data-cleaning` skill to LangGraph state graph
- [ ] 5.6 Migrate `feature-engineering` skill to LangGraph state graph
- [ ] 5.7 Migrate `model-training` skill to LangGraph state graph (parallel training + conditional gate routing)
- [ ] 5.8 Write integration test verifying full skill execution through LangGraph for each skill

## 6. DeepSeek Integration

- [ ] 6.1 Add DeepSeek provider config template to `config.yaml` defaults
- [ ] 6.2 Write integration test: OpenAIClient against DeepSeek V4 Flash (chat + streaming + tool calling)
- [ ] 6.3 Verify model switching between DeepSeek and other providers at runtime

## 7. API Extensions

- [ ] 7.1 Add WebSocket endpoint (`GET /ws`) to `api/app.py` with connection management
- [ ] 7.2 Implement WebSocket event types: `lineage_update`, `decision_update`, `phase_transition`, `token_stream`
- [ ] 7.3 Add `POST /upload` endpoint for drag-and-drop file upload
- [ ] 7.4 Hook gate approval endpoint to LangGraph resume (update `POST /skill/gate`)
- [ ] 7.5 Add WebSocket broadcast on phase transitions in LangGraphAgent
- [ ] 7.6 Write integration tests for WebSocket and new endpoints

## 8. Web UI — Vue 3 SPA

- [ ] 8.1 Scaffold `web-ui/` project with Vite + Vue 3 + TypeScript + Pinia
- [ ] 8.2 Implement three-panel layout (`App.vue` with `DataSidebar`, `ChatPanel`, `ContextPanel`)
- [ ] 8.3 Implement Dark mode toggle with persisted preference (Pinia store + CSS variables)
- [ ] 8.4 Implement `DataSidebar.vue`: dataset listing with raw/processed grouping, drag-drop upload zone
- [ ] 8.5 Implement `ChatPanel.vue`: message display, input box, `/skill` command parsing, SSE token streaming
- [ ] 8.6 Implement `CodeBlock.vue`: syntax-highlighted code display with "View in Scripts" link
- [ ] 8.7 Implement `GateApproval.vue`: interactive Approve/Reject buttons embedded in chat
- [ ] 8.8 Implement `ContextPanel.vue`: lineage graph, decisions list, parameters display
- [ ] 8.9 Implement `LineageGraph.vue`: D3.js or Cytoscape.js lineage graph visualization with real-time updates
- [ ] 8.10 Implement `useWebSocket.ts` composable for WebSocket connection lifecycle
- [ ] 8.11 Implement `useChat.ts` composable for chat state and SSE streaming
- [ ] 8.12 Implement Pinia `session` store for global state management
- [ ] 8.13 Configure Vite dev server proxy to FastAPI backend
- [ ] 8.14 Configure FastAPI to serve built Vue static files in production
- [ ] 8.15 Write E2E test: full flow — upload CSV → invoke /skill data-cleaning → approve gate → see lineage update

## 9. Final Integration and Verification

- [ ] 9.1 Run full test suite (unit + integration + e2e), ensure all 185+ tests pass
- [ ] 9.2 Run `comet-state check datamind-engine-v3 build` to verify state before guard transition
- [ ] 9.3 Verify all 6 spec files exist and are non-empty
- [ ] 9.4 Confirm DeepSeek V4 Flash integration passes the dedicated test
- [ ] 9.5 Confirm Web UI builds and serves correctly from FastAPI
