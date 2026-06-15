# Brainstorm Summary

- Change: datamind-engine-v3
- Date: 2026-06-15

## Confirmed Technical Approach

**LangGraph Node Granularity — Mixed strategy**
- Simple linear skills: one node per phase, straightforward StateGraph edges
- Complex skills (model-training): `Send` API for parallel execution + conditional edges for REJECT routing
- `SkillGraphBuilder` auto-detects: if skill has `parallel` or `routing` in YAML frontmatter → complex graph; otherwise → linear

**Dual-Channel Communication**
- SSE (`/chat/stream`) for token streaming — auto-reconnect, built-in `event:` framing
- WebSocket (`/ws`) for real-time events (lineage_update, decision_update, phase_transition) + client-to-server commands (chat_message, skill_invoke, gate_decision)
- Frontend: `useChat.ts` composable (EventSource) + `useWebSocket.ts` composable (WebSocket)

**SKILL.md Extension — YAML frontmatter**
- Backward-compatible: existing skills without frontmatter default to linear behavior
- Machine-readable YAML: routing rules, per-phase tool declarations, parallel config
- Human-readable markdown body: phase descriptions unchanged
- `SkillParser` already handles YAML frontmatter + markdown (same pattern as prompt templates)

**Checkpointer — SqliteSaver (sync)**
- Write operations via `run_in_executor` to avoid blocking FastAPI event loop
- No additional dependencies (sqlite3 is stdlib)
- `checkpoints.db` lives in session directory alongside `.skill.yaml`

**Vue 3 Component Library — Element Plus**
- Vue 3 native, built-in dark mode, comprehensive components (layout, form, dialog, upload)
- Chinese documentation, larger ecosystem
- CSS variables for theme customization

**Tool Sandbox — subprocess + TemporaryDirectory**
- Scripts execute in `tempfile.TemporaryDirectory` — limits filesystem side effects
- Timeout (300s default) + output size limit (1MB)
- Zero additional dependencies

## Key Trade-offs and Risks

- **[Risk] LangGraph API instability (<1.0)** → Pin version, isolate via `engine/langgraph_agent.py`
- **[Risk] SqliteSaver blocking event loop** → `run_in_executor` with thread pool; checkpoint writes are <1ms
- **[Trade-off] Dual channel (SSE + WS) vs single WebSocket** → Two connections but each is simpler; avoids reimplementing SSE semantics on WebSocket
- **[Trade-off] Element Plus vs lighter alternatives** → Slightly heavier bundle but saves weeks of custom component work
- **[Trade-off] subprocess sandbox vs Docker** → Trusted user model sufficient for v3; Docker added complexity without matching benefit

## Testing Strategy

- **TDD first**: every module starts with RED test, then GREEN implementation
- **Tool system**: unit test per tool (+ TDD gate), integration test for ToolRegistry end-to-end
- **LangGraph agent**: unit tests for SkillGraphBuilder output (verify graph structure), state transitions, interrupt/resume cycle
- **Agent wrapper**: existing `DataMindAgent` tests must pass through the thin wrapper unchanged
- **Skill migration**: one integration test per skill (full LangGraph execution with mock LLM)
- **DeepSeek**: dedicated integration test (chat + streaming + tool calling against real API)
- **API**: WebSocket lifecycle test, upload endpoint test, gate approval through LangGraph resume
- **Web UI**: E2E test (Playwright) for full flow: upload → chat → /skill → gate approve → lineage update
- **Regression**: all 185 existing tests must pass at every step

## Spec Patches

None — all delta specs are complete and confirmed. No requirement changes during brainstorming.
