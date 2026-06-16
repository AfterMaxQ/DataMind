# Comet Design Handoff

- Change: datamind-engine-v3
- Phase: design
- Mode: compact
- Context hash: 817967ee25115543db2be3319ba13790aa5f63342dad0ed638d602d781a83df9

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/datamind-engine-v3/proposal.md

- Source: openspec/changes/datamind-engine-v3/proposal.md
- Lines: 1-54
- SHA256: 6c0d15e8e375d59507cf957856ebf329c572ee0d4f0b2ca95c69348dba97ff2d

```md
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
```

## openspec/changes/datamind-engine-v3/design.md

- Source: openspec/changes/datamind-engine-v3/design.md
- Lines: 1-196
- SHA256: 902a9e83b183877eee95fec4952764fc59b0354cfaa70599a2482643f82013c8

[TRUNCATED]

```md
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
```

Full source: openspec/changes/datamind-engine-v3/design.md

## openspec/changes/datamind-engine-v3/tasks.md

- Source: openspec/changes/datamind-engine-v3/tasks.md
- Lines: 1-91
- SHA256: bb48b4081b70531bc239f3496b9515f7c4e8de592ba6f5c9c7a89d37aac22168

[TRUNCATED]

```md
﻿## 1. Setup and Dependencies

- [ ] 1.1 Add `langgraph` to pyproject.toml dependencies
- [ ] 1.2 Run `pip install -e ".[dev]"` to install langgraph
- [ ] 1.3 Verify all 185 existing tests pass on current master

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
```

Full source: openspec/changes/datamind-engine-v3/tasks.md

## openspec/changes/datamind-engine-v3/specs/agent-execution/spec.md

- Source: openspec/changes/datamind-engine-v3/specs/agent-execution/spec.md
- Lines: 1-64
- SHA256: d9be751256c3372b63e1b565a8337a6f9a20a4cb6d0217d2d9ba9e6ef0b0627c

```md
﻿## MODIFIED Requirements

### Requirement: Agent Loop
The system SHALL provide an agent execution loop powered by LangGraph state graphs. Each skill invocation SHALL construct a `StateGraph` from the skill`s phase definitions. AUTO phases SHALL be executed via LLM-tool interaction loops. GATE phases SHALL pause execution using LangGraph`s `interrupt()` primitive and resume on human approval. The execution loop SHALL support conditional branching (REJECT routes to a designated fallback node), parallel execution of independent nodes, and map-reduce fan-out patterns.

#### Scenario: AUTO phase executes
- **WHEN** a skill execution reaches an AUTO phase
- **THEN** the LangGraph agent assembles context, renders the system prompt, calls the LLM with tool definitions, executes tool calls in a loop, and records decisions before advancing to the next node

#### Scenario: GATE phase pauses execution
- **WHEN** a skill execution reaches a GATE phase
- **THEN** LangGraph`s `interrupt()` pauses execution and returns a `WaitForApproval` event with the phase ID, name, and context message

#### Scenario: Gate approval resumes execution
- **WHEN** the human approves the GATE with a decision
- **THEN** LangGraph resumes from the interrupt point and routes to the next node based on the decision

#### Scenario: Gate rejection routes back
- **WHEN** the human rejects the GATE with action "reject"
- **THEN** the graph routes to the designated fallback phase (e.g., back to proposal) via a conditional edge

#### Scenario: Parallel phase execution
- **WHEN** a skill phase specifies parallel candidate execution
- **THEN** LangGraph spawns independent sub-graphs for each candidate, executes them concurrently, and merges results before continuing

#### Scenario: Tool calls execute during AUTO phases
- **WHEN** the LLM requests tool execution during an AUTO phase
- **THEN** the LangGraph agent dispatches to ToolRegistry, collects results, and feeds them back to the LLM for up to 5 tool turns

### Requirement: Skill State Machine
The system SHALL provide a `SkillStateMachine` that tracks skill execution phases, their status (pending, in_progress, completed, rejected), and their artifacts. The state machine SHALL persist to `.skill.yaml` and integrate with LangGraph checkpoints via `SqliteSaver`.

#### Scenario: Skill state machine manages phases
- **WHEN** a new skill session is created
- **THEN** the state machine initializes all phases as pending and persists the initial state to `.skill.yaml`

#### Scenario: Phase completion updates state
- **WHEN** an AUTO phase completes execution
- **THEN** the phase status is set to completed in `.skill.yaml` and a LangGraph checkpoint is written to `checkpoints.db`

### Requirement: Interrupt and Resume
The system SHALL support interrupt and resume of skill execution via LangGraph checkpoints. On interruption, LangGraph`s `SqliteSaver` SHALL persist the full graph state. On resume, the agent SHALL restore from the checkpoint and continue from the interrupted node. Additionally, `.skill.yaml` SHALL provide a lightweight summary for discovery without loading LangGraph.

#### Scenario: Resume after interruption via LangGraph
- **WHEN** a skill execution is interrupted (process restart, crash)
- **THEN** the agent loads the graph from `checkpoints.db`, restores the full state including messages and tool results, and continues from the interrupted node

#### Scenario: Fast status check via .skill.yaml
- **WHEN** the API needs to display session status without loading LangGraph
- **THEN** it reads `.skill.yaml` (~200 bytes) to get skill name, current phase, phase statuses, and result

### Requirement: Skill Session Artifact Tracking
The system SHALL track artifacts created during skill execution. Phase outputs SHALL be stored as markdown or JSON files in the session directory. LangGraph checkpoints SHALL reference artifact paths in the graph state.

#### Scenario: Artifacts tracked in session directory
- **WHEN** an AUTO phase produces output
- **THEN** the output is written to the session directory and the artifact path is stored in both the LangGraph state and `.skill.yaml`

### Requirement: Framework-Agnostic Design
The system SHALL use LangGraph as the agent execution framework. The LLM client layer (`engine/llm.py`) SHALL remain framework-agnostic, exposing a chat completion interface that LangGraph can call. This preserves the ability to swap LLM providers independently of the graph framework.

#### Scenario: LLM client used by LangGraph agent
- **WHEN** the LangGraph agent needs to call the LLM
- **THEN** it invokes `llm_client.chat(messages, tools)` — the same interface used by v2`s custom agent loop
```

## openspec/changes/datamind-engine-v3/specs/langgraph-integration/spec.md

- Source: openspec/changes/datamind-engine-v3/specs/langgraph-integration/spec.md
- Lines: 1-59
- SHA256: 611288539ed5561ed811f164bccfd3a18bca043ed724a923d5618fc40f6f8f4d

```md
﻿## ADDED Requirements

### Requirement: LangGraph State Graph per Skill
The system SHALL construct a LangGraph `StateGraph` for each skill definition. Each skill phase SHALL become a graph node. Phase transitions SHALL become graph edges. AUTO phases SHALL execute via LLM-tool loops. GATE phases SHALL pause execution via LangGraph `interrupt()` and resume on human approval.

#### Scenario: Linear AUTO → GATE graph execution
- **WHEN** a skill with phases [AUTO:analyze, GATE:review, AUTO:execute] is invoked
- **THEN** the LangGraph agent executes the analyze node, pauses at the review node, and resumes through the execute node after gate approval

#### Scenario: Graph construction from skill definition
- **WHEN** a SKILL.md with phase definitions is parsed
- **THEN** `SkillGraphBuilder` produces a valid `StateGraph` with one node per phase and edges matching the phase order

### Requirement: Conditional Branching on Gate Decisions
The system SHALL support conditional routing from GATE nodes. When a human APPROVEs, execution SHALL continue to the next phase. When a human REJECTs, execution SHALL route to a designated fallback node (typically the preceding proposal phase).

#### Scenario: Reject routes back to proposal
- **WHEN** a human REJECTs a GATE with the decision `{"action": "reject"}`
- **THEN** the graph routes to the fallback phase specified in the skill definition (e.g., back to "Propose Strategy")

#### Scenario: Approve continues forward
- **WHEN** a human APPROVEs a GATE with the decision `{"action": "approve"}`
- **THEN** the graph routes to the next phase in the skill sequence

### Requirement: Parallel Execution Nodes
The system SHALL support parallel execution of independent AUTO nodes via LangGraph`s `Send` API. Parallel nodes SHALL execute concurrently and their outputs SHALL be merged before continuing to the next phase.

#### Scenario: Parallel model training
- **WHEN** the model-training skill reaches the "Train" phase with 3 candidate models
- **THEN** each model is trained in a parallel LangGraph node and results are aggregated before the "Evaluate" phase

#### Scenario: Single model falls back to sequential
- **WHEN** the model-training skill reaches the "Train" phase with only 1 candidate model
- **THEN** a single training node executes (no parallel overhead)

### Requirement: Map-Reduce Fan-Out Validation
The system SHALL support map-reduce patterns where validation checks are fanned out across multiple dimensions (correctness, performance, security) and results are reduced into a single validation report.

#### Scenario: Fan-out validation after code generation
- **WHEN** a script is generated in the "Execute" phase
- **THEN** validation checks run in parallel across correctness, style, and performance dimensions, and a merged report is produced

### Requirement: Checkpoint and Resume
The system SHALL use LangGraph`s `SqliteSaver` checkpointer to persist graph state on every transition. On resume, the graph SHALL restore to the exact state before interruption, including all messages, tool results, and phase outputs.

#### Scenario: Resume after interruption
- **WHEN** a skill session is interrupted mid-execution (process restart, crash)
- **THEN** the agent loads the graph from `checkpoints.db` and continues from the interrupted node without re-executing completed phases

#### Scenario: Checkpoint written on gate pause
- **WHEN** execution pauses at a GATE node
- **THEN** a checkpoint is persisted to `checkpoints.db` capturing the current graph state

### Requirement: .skill.yaml Coexistence
The system SHALL maintain `.skill.yaml` alongside LangGraph checkpoints. `.skill.yaml` SHALL contain a human-readable summary of the session: skill name, target, current phase, phase statuses, and result. The checkpoints.db SHALL contain the full machine-recoverable graph state.

#### Scenario: Both files updated on transition
- **WHEN** a phase transition occurs in the LangGraph agent
- **THEN** both `checkpoints.db` (checkpoint) and `.skill.yaml` (summary) are updated
```

## openspec/changes/datamind-engine-v3/specs/llm-integration/spec.md

- Source: openspec/changes/datamind-engine-v3/specs/llm-integration/spec.md
- Lines: 1-23
- SHA256: 5914df0ca12db061d1029ef5fb15ca258aa173a0b44368d40af99c6e72b12b56

```md
﻿## MODIFIED Requirements

### Requirement: LLM Client Abstraction
The system SHALL provide a unified `BaseLLMClient` interface with concrete implementations for OpenAI-compatible APIs (`OpenAIClient`) and Ollama local models (`OllamaClient`). The `OpenAIClient` SHALL be verified against DeepSeek`s OpenAI-compatible API as a supported provider. All implementations SHALL support chat completion, streaming, and tool calling with retry on transient errors (429, 502, 503).

#### Scenario: DeepSeek V4 Flash via OpenAIClient
- **WHEN** the LLM client is configured with `provider: openai`, `api_base: https://api.deepseek.com`, `model: deepseek-v4-flash`
- **THEN** chat completion, streaming, and tool calling all work correctly via the `OpenAIClient`

#### Scenario: OpenAIClient works with any OpenAI-compatible provider
- **WHEN** the LLM client is configured with any OpenAI-compatible `api_base` and `model`
- **THEN** the `OpenAIClient` sends correctly formatted requests and parses responses, regardless of the specific provider

### Requirement: LLM Configuration
The system SHALL load LLM configuration from `.datamind/config.yaml` with `${ENV_VAR}` environment variable injection. The configuration template SHALL include pre-configured provider entries for DeepSeek, OpenAI, and Ollama with their default `api_base` URLs and model lists.

#### Scenario: DeepSeek configured via config.yaml
- **WHEN** `.datamind/config.yaml` contains a `deepseek` provider entry with `api_base`, `api_key`, and `models`
- **THEN** the system creates an `OpenAIClient` pointed at the DeepSeek API

#### Scenario: Env var injection for API key
- **WHEN** the config contains `api_key: "${DEEPSEEK_API_KEY}"`
- **THEN** the value is resolved from the `DEEPSEEK_API_KEY` environment variable at load time
```

## openspec/changes/datamind-engine-v3/specs/skill-system/spec.md

- Source: openspec/changes/datamind-engine-v3/specs/skill-system/spec.md
- Lines: 1-27
- SHA256: 92efbe851dc7d504ffbcf220b4d9108d6a028ca330f158c9dd351fcc76d8dfc9

```md
﻿## MODIFIED Requirements

### Requirement: Skill Execution Context
The system SHALL provide skills with access to a shared execution context that includes the project`s `ToolRegistry`. Skills SHALL be able to invoke registered tools (data I/O, describe, script generation, script execution) during AUTO phases. Tool definitions SHALL be dynamically injected into LLM context for each AUTO phase.

#### Scenario: Tool definitions injected for skill execution
- **WHEN** a skill enters an AUTO phase
- **THEN** the LangGraph agent queries `ToolRegistry.get_definitions()` and includes all tool schemas in the LLM request

#### Scenario: Skill invokes data read tool
- **WHEN** a data-cleaning skill`s "Analyze" phase needs to inspect a CSV file
- **THEN** the LLM can call `read_csv` to get the schema and sample, and the result is fed back into the conversation

#### Scenario: Skill generates and executes a script
- **WHEN** a data-cleaning skill`s "Execute" phase needs to run a cleaning script
- **THEN** the LLM calls `generate_script` to create the script, then `execute_script` to run it in the sandbox, and captures the output

### Requirement: Tool-Aware Phase Definitions
The system SHALL support skill phase definitions that declare which tools are available during that phase. Tool availability SHALL be scoped per-phase: a "Generate" phase may have `generate_script` and `execute_script`, while an "Analyze" phase may have `read_csv`, `read_parquet`, and `describe_dataset`.

#### Scenario: Phase-scoped tool availability
- **WHEN** a SKILL.md phase definition includes `tools: [read_csv, describe_dataset]`
- **THEN** only those tools are injected into the LLM context for that phase

#### Scenario: Phase without explicit tools gets all
- **WHEN** a SKILL.md phase definition does not specify tools
- **THEN** all registered tools are available during that phase
```

## openspec/changes/datamind-engine-v3/specs/tool-execution/spec.md

- Source: openspec/changes/datamind-engine-v3/specs/tool-execution/spec.md
- Lines: 1-67
- SHA256: e00b8658d7917069b5572317432380c1b92908079b1e47f13321ca7fb7eee466

```md
﻿## ADDED Requirements

### Requirement: Tool Registry
The system SHALL provide a `ToolRegistry` that stores all available tool definitions as `(schema, callable)` pairs. Tools SHALL be registered at engine startup. The registry SHALL expose `get_definitions()` returning the full tool schema list for LLM injection, and `execute(name, args)` dispatching execution to the registered callable.

#### Scenario: Register and execute a tool
- **WHEN** a tool is registered with name, JSON schema, and callable
- **THEN** `get_definitions()` includes that tool`s schema and `execute(name, args)` invokes the callable with the given arguments

#### Scenario: Unknown tool returns error
- **WHEN** `execute` is called with a tool name not in the registry
- **THEN** an error result is returned with a message indicating the tool is unknown

### Requirement: Data I/O Tools
The system SHALL provide tools for reading common data formats. Each read tool SHALL accept a file path and return the dataset schema (column names, inferred types) plus a sample of the first N rows (default 10).

#### Scenario: Read CSV with auto-detect
- **WHEN** `read_csv` is called with a path to a valid CSV file
- **THEN** the tool returns column names, inferred dtypes, row count, and first 10 rows as JSON

#### Scenario: Read Parquet file
- **WHEN** `read_parquet` is called with a path to a valid Parquet file
- **THEN** the tool returns the schema and sample rows

#### Scenario: Read Excel file
- **WHEN** `read_excel` is called with a path to a valid Excel file
- **THEN** the tool returns sheet names, schema per sheet, and sample rows

#### Scenario: Read non-existent file returns error
- **WHEN** any read tool is called with a path that does not exist
- **THEN** an error result is returned with a "file not found" message

### Requirement: Auto-Describe Tool
The system SHALL provide a `describe_dataset` tool that auto-generates a data description for any registered dataset. The description SHALL include: row count, column count, column names, inferred types, null counts and percentages, unique value counts, and basic distribution statistics for numeric columns.

#### Scenario: Describe a CSV dataset
- **WHEN** `describe_dataset` is called with a registered dataset path
- **THEN** a description is generated and saved to `describe/<filename>.describe.md`, and the dataset node is created in graph.db

### Requirement: Script Generation Tool
The system SHALL provide a `generate_script` tool that creates Python scripts from templates. The tool SHALL accept a template name, parameters dict, and output path. Generated scripts SHALL be executable and include metadata comments identifying them as AI-generated.

#### Scenario: Generate a cleaning script
- **WHEN** `generate_script` is called with template "data-cleaning", parameters {"input": "sales.csv", "operations": ["drop_nulls", "normalize"]}, and output path "scripts/clean_sales.py"
- **THEN** a valid Python script is written to the output path with the specified operations

### Requirement: Script Execution Sandbox
The system SHALL provide an `execute_script` tool that runs a Python script in a subprocess. Execution SHALL have a configurable timeout (default 300 seconds). Stdout and stderr SHALL be captured and returned. The tool SHALL enforce a maximum output size limit (default 1MB).

#### Scenario: Execute a script successfully
- **WHEN** `execute_script` is called with a valid Python script path
- **THEN** the script runs in a subprocess and stdout, stderr, and exit code are returned

#### Scenario: Script timeout
- **WHEN** a script exceeds the configured timeout
- **THEN** the subprocess is terminated and an error result with "timeout" is returned

#### Scenario: Script with error
- **WHEN** a script raises an exception
- **THEN** the exit code is non-zero and stderr contains the traceback

### Requirement: Tool Definitions for LLM Context
The system SHALL generate OpenAI-compatible tool definitions from the `ToolRegistry` for injection into LLM requests. Each tool definition SHALL include a name, description, and JSON Schema `parameters` object.

#### Scenario: Tool definitions injected into LLM call
- **WHEN** the LangGraph agent prepares an LLM call for an AUTO phase
- **THEN** the `tools` parameter includes definitions for all registered tools
```

## openspec/changes/datamind-engine-v3/specs/web-ui/spec.md

- Source: openspec/changes/datamind-engine-v3/specs/web-ui/spec.md
- Lines: 1-64
- SHA256: 67f19306a2d380c2e5a3905d944fa7b1aa2e2ec217d1bffea16110eafc40232a

```md
﻿## MODIFIED Requirements

### Requirement: Three-Panel Layout
The system SHALL provide a Vue 3 web interface with three panels: a left sidebar for data and script browsing, a central panel for AI dialogue, and a right panel for context visualization. The layout SHALL support Dark mode toggle.

#### Scenario: Default layout
- **WHEN** user opens the web UI
- **THEN** all three panels are visible: sidebar (data/files), center (chat), right (lineage + context)

#### Scenario: Dark mode toggle
- **WHEN** user clicks the dark mode toggle
- **THEN** the entire UI switches between light and dark color schemes, and the preference is persisted

### Requirement: Data Sidebar
The left sidebar SHALL display datasets organized by raw/ and processed/ folders. Each dataset entry SHALL show name, row count, column count, and a link to its generating script (for processed datasets). The sidebar SHALL support drag-and-drop file upload for adding new raw datasets.

#### Scenario: Drag and drop CSV upload
- **WHEN** user drags a CSV file from their desktop onto the sidebar
- **THEN** the file is uploaded via `POST /upload`, copied to `data/raw/`, a Dataset node is created in graph.db, and a describe file is auto-generated

#### Scenario: Click processed dataset for lineage
- **WHEN** user clicks a processed dataset in the sidebar
- **THEN** the right panel highlights the dataset`s position in the lineage graph and shows its generating script

### Requirement: Chat Panel
The central panel SHALL provide a dialogue interface where users can type messages to the AI, invoke skills with `/skill` commands, and see AI responses including proposed code, analysis results, and gate approval prompts. Generated code SHALL be displayed inline with syntax highlighting. SSE streaming SHALL display tokens as they arrive. Gate prompts SHALL be rendered as interactive approval/rejection buttons.

#### Scenario: Chat interaction
- **WHEN** user types a message in the chat input
- **THEN** the message appears in the conversation and the AI responds based on project context, streaming tokens via SSE

#### Scenario: Skill invocation display
- **WHEN** user invokes `/skill data-cleaning sales.csv`
- **THEN** the chat shows the skill workflow steps as they execute, with gate prompts rendered as interactive approval buttons

#### Scenario: Code display
- **WHEN** AI generates a processing script
- **THEN** the code is displayed inline with syntax highlighting and a "View in Scripts" link

#### Scenario: Gate approval
- **WHEN** a skill reaches a GATE phase
- **THEN** an interactive approval panel appears with Approve and Reject buttons, and the user`s decision is sent via `POST /skill/gate`

### Requirement: Context Panel
The right panel SHALL display the live lineage graph, recent decisions from decisions.jsonl, and active parameters from params.json. The lineage graph SHALL update in real-time via WebSocket when new datasets and scripts are created. The panel SHALL also show the current skill execution status including the active phase and phase transitions.

#### Scenario: Lineage graph updates via WebSocket
- **WHEN** a new script is generated and executed
- **THEN** the lineage graph in the right panel adds the new node and edge immediately via WebSocket `lineage_update` event

#### Scenario: Decision log display
- **WHEN** a new decision is recorded in decisions.jsonl
- **THEN** the recent decisions list in the right panel shows the new entry via WebSocket `decision_update` event

#### Scenario: Skill phase transition display
- **WHEN** a skill phase transitions (pending → in_progress → completed)
- **THEN** the context panel shows the current phase status via WebSocket `phase_transition` event

### Requirement: Session Context Indicator
The web UI SHALL display the current context status: whether context has been loaded, the last session timestamp, the current checkpoint version, and a summary of what was injected.

#### Scenario: Context status display
- **WHEN** a new session starts
- **THEN** the UI shows "Context: Ready" with details of what was injected (datasets, decisions, checkpoint version)
```

