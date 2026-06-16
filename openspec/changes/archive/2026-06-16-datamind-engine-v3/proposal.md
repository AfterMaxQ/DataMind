# datamind-engine-v3

## Why

v2 turned the engine from a passive recorder into an active AI execution system with LLM integration, an agent loop, and a skill state machine. But the agent loop is purely linear—no branching, no parallelism, no conditional routing. Tools are stubs (`_get_tool_defs()` returns `[]`). And the Web UI exists only as a spec. v3 makes DataMind Studio a complete AI data science workstation: complex LangGraph-driven workflows, real data tools that actually execute, and a full Vue 3 web interface.

## What Changes

### LangGraph Integration (new)
- Replace custom while-loop in `engine/agent.py` with LangGraph state graphs
- Support conditional branching: REJECT at GATE → loop back to proposal phase
- Support parallel execution: train multiple models simultaneously, compare results
- Support map-reduce patterns: fan-out validation across dimensions
- Built-in checkpoint/resume via LangGraph checkpointer (supplements `.skill.yaml`)
- All 7 skills migrated to LangGraph state graphs

### Real Tool Execution (new)
- Minimum viable tool set: CSV/Parquet/Excel read, auto-describe generation, script generation & sandbox execution
- Tools are no longer stubs—skills can actually read data, inspect schemas, execute scripts
- Script sandbox: subprocess-isolated Python execution with output capture
- Tool definitions dynamically generated and injected into LLM context

### Web UI — Vue 3 SPA (new implementation)
- Vue 3 three-panel layout: data sidebar, chat panel, context panel
- Drag-and-drop CSV upload → auto-register + describe
- Chat panel with `/skill` command support, syntax-highlighted code, interactive Gate approval buttons
- Real-time lineage graph and decision updates via WebSocket
- Dark mode
- Session context indicator

### DeepSeek V4 Flash Integration
- DeepSeek V4 Flash verified as an OpenAI-compatible provider via existing `OpenAIClient`
- Default test model: `deepseek-v4-flash` at `https://api.deepseek.com`
- LLM config template includes DeepSeek as a pre-configured provider option

## Capabilities

### New Capabilities
- `langgraph-integration`: LangGraph state graphs with conditional edges, parallel execution, map-reduce patterns, and checkpoint/resume
- `tool-execution`: Real tool implementations for data I/O (CSV/Parquet/Excel), auto-describe, script generation, and subprocess sandbox execution

### Modified Capabilities
- `agent-execution`: Agent loop requirement changed from custom while-loop to LangGraph state graph; new requirements for conditional branching, parallel execution, and checkpoint/resume
- `skill-system`: Skill execution context requirement changed—skills must execute real tool calls; new requirement for tool-aware phase definitions
- `web-ui`: Added requirements for WebSocket real-time updates and Dark mode; existing requirements now marked for Vue 3 implementation
- `llm-integration`: Added DeepSeek as verified provider; new requirement for provider configuration template with pre-configured providers

## Impact

- **New modules**: `engine/langgraph_agent.py` (LangGraph state graph builder), `engine/tools.py` (tool implementations), `web-ui/` (Vue 3 SPA project)
- **Modified modules**: `engine/agent.py` (replaced or rewritten), `engine/skills.py` (tool-aware skill execution), `api/app.py` (WebSocket endpoints + new REST endpoints), `engine/skill_state.py` (checkpoint integration)
- **New dependencies**: `langgraph` (LangGraph Python SDK), Vue 3 ecosystem (`vue`, `vite`, `pinia`)
- **Breaking**: `DataMindAgent` public API replaced by LangGraph-based agent; `_get_tool_defs()` and `_tool_executor` removed in favor of `engine/tools.py`; agent loop no longer a simple while-loop
- **Tests**: 185 existing tests must continue passing; new tests for LangGraph state graphs, tool execution, and Web UI
