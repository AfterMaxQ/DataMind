# Comet Design Handoff

- Change: datamind-engine-v2
- Phase: design
- Mode: compact
- Context hash: c0d0530a65bbfd782dd5b39d0527794a3755b2b55be9f19d416d3c3320e777dc

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/datamind-engine-v2/proposal.md

- Source: openspec/changes/datamind-engine-v2/proposal.md
- Lines: 1-53
- SHA256: 94f1379b3e60d6655657ee5876b192c681eccc84d7821ea2bbe395137e7db2a0

```md
# datamind-engine-v2

## Why

v1 established the four-layer engine (data lineage, cognitive journey, context assembly, skill system) — but the execution brain is missing. There's no LLM integration, no agent loop, and the skill system only parses definitions without executing them. Skills are linear JSON loops with no state machine, no interrupt/resume, no phase tracking. v2 turns the engine from a passive recorder into an active AI execution system.

## What Changes

### LLM Integration (new)
- LLM client abstraction supporting OpenAI-compatible APIs and Ollama local models
- Multi-model switching at runtime with auto-discovery of Ollama models via `ollama list`
- System prompt templates as markdown files in a directory, with variable injection
- Token usage and cost tracking aggregated per session
- LLM configuration via `.datamind/config.yaml` and environment variable injection (both supported)

### Agent Execution (new)
- Agent loop: assemble context → build prompt → call LLM → execute tools → record decisions
- Framework-agnostic LLM client design, reserving LangGraph migration path for v3
- Skill Session state machine: `.skill.yaml` lifecycle with phase tracking and artifact management
- Interrupt/resume: AI reads `.skill.yaml` and recovers to the exact phase, no re-execution needed

### Skill System — Major Rewrite
- All 7 skills rewritten with Comet-style phase definitions and state machine
- New skills: `requirement-discussion` (problem framing), `auto-archive` (project phase archival)
- Existing skills rewritten: `data-cleaning`, `data-exploration`, `feature-engineering`, `model-training`, `report-generation`
- `SkillSession` + `SkillStateMachine` replace v1's parse-only `SkillService`
- Each skill session produces timestamped artifact directories under `.datamind/skill-sessions/`

### L1-L3 Extensions
- Materialized view rebuild from `executions/` (event sourcing read path)
- Reproducibility: lineage traceback + script chain replay
- Context file auto-refresh on state change
- Chat SSE streaming endpoint in API

## Capabilities

### New Capabilities
- `llm-integration`: LLM client abstraction (OpenAI-compatible + Ollama), multi-model switching, prompt template management, usage tracking
- `agent-execution`: Agent loop orchestrating context → LLM → tools → decisions, skill session state machine with interrupt/resume, framework-agnostic for v3 LangGraph migration

### Modified Capabilities
- `data-lineage`: Add reproducibility (lineage traceback + script chain replay) and materialized view rebuild
- `context-assembly`: Add auto-refresh triggered by state changes
- `skill-system`: Replace parse-only SkillService with SkillSession + SkillStateMachine; phase-based skill definitions; `.skill.yaml` lifecycle management

## Impact

- **New modules**: `engine/llm.py`, `engine/prompt.py`, `engine/agent.py`, `engine/usage.py`, `engine/skill_state.py`
- **Extended modules**: `engine/skills.py` (rewrite), `engine/events.py`, `engine/lineage.py`, `engine/assembly.py`, `config.py`, `api/app.py`
- **New skills**: `skills/requirement-discussion.md`, `skills/auto-archive.md`
- **Rewritten skills**: `skills/data-cleaning.md`, `skills/data-exploration.md`, `skills/feature-engineering.md`, `skills/model-training.md`, `skills/report-generation.md`
- **Dependencies**: `ollama` (optional, for local model auto-discovery), `openai` Python SDK, `pyyaml`
- **Breaking**: `SkillService` and `SkillParser` public API replaced; skill execution flow changes
```

## openspec/changes/datamind-engine-v2/design.md

- Source: openspec/changes/datamind-engine-v2/design.md
- Lines: 1-153
- SHA256: 31fbf1cc7c7e53613583f9363ec254a1b8cad0f9eb9090e749d421df644b056c

[TRUNCATED]

```md
## Context

v1 established the four-layer engine: L1 Data Lineage (graph.db, describe, scripts), L2 Cognitive Journey (decisions, exploration, params, discoveries), L3 Context Assembly (priority-ordered context packing), L4 Skill System (SKILL.md parsing, AUTO/GATE step tracking). v1's skill system is parse-only — it reads SKILL.md files and tracks step state, but has no execution engine. There is no LLM integration, no agent loop, and skills cannot be interrupted and resumed efficiently.

v2 adds the execution brain: LLM clients, an agent loop, and a Comet-style skill state machine that enables fast interrupt/resume with minimal context re-reading.

The design must remain framework-agnostic at the LLM client layer, reserving a LangGraph migration path for v3 when complex branching/parallel skill pipelines emerge.

## Goals / Non-Goals

**Goals:**
- LLM client abstraction supporting OpenAI-compatible APIs and Ollama local models
- Multi-model switching at runtime with auto-discovery of Ollama models
- System prompt templates as directory of markdown files with variable injection
- Per-session token usage and cost tracking
- Agent loop: context assembly → prompt → LLM call → tool execution → decision recording
- Skill state machine with `.skill.yaml` lifecycle, phase tracking, artifact management
- Interrupt/resume: AI reads `.skill.yaml` and recovers to exact phase without re-execution
- 7 skills rewritten with phase-based definitions (5 existing + 2 new)
- Materialized view rebuild from execution logs, reproducibility, and context auto-refresh
- Chat SSE streaming endpoint

**Non-Goals:**
- Vue 3 Web UI (separate `datamind-web-ui` change)
- LangGraph integration (v3, architecture reserved)
- RAG / vector retrieval / embeddings
- Multi-agent collaboration
- Real-time WebSocket updates beyond SSE

## Decisions

### D1: LLM Client — Custom abstraction over framework

**Decision**: Build a thin `BaseLLMClient` abstract class with `OpenAIClient` and `OllamaClient` implementations. Do NOT use LangChain's LLM abstraction.

**Rationale**: LangChain's LLM wrapper adds ~15 dependencies and abstraction overhead without adding value. The OpenAI Python SDK already provides a clean interface. Ollama exposes an OpenAI-compatible endpoint. The abstraction is ~50 lines, not a framework.

**Alternatives considered**:
- LangChain LLM: Heavy dependency, frequent breaking changes, little benefit over direct SDK calls
- LiteLLM: Good multi-provider proxy but adds a proxy layer; overkill for v2's two providers

### D2: Agent Loop — Custom lightweight, LangGraph-reserved

**Decision**: Implement a custom agent loop in `engine/agent.py` (~120 lines). The LLM client layer (`engine/llm.py`) is designed to be framework-agnostic. When v3 requires LangGraph for complex branching/parallel execution, only `engine/agent.py` needs replacement.

**Rationale**: v2's skill execution is linear (AUTO → GATE → AUTO → GATE). A custom while-loop with interrupt/resume is simpler and more transparent than LangGraph for linear flows. The architecture boundary at `engine/llm.py` ensures framework independence.

**LangGraph migration trigger (v3)**: When skills need parallel execution (multi-model training), conditional branching (REJECT → back to propose), or map-reduce patterns (fan-out validation).

### D3: Skill State Machine — `.skill.yaml` as source of truth

**Decision**: Each skill invocation creates a timestamped session directory under `.datamind/skill-sessions/` containing a `.skill.yaml` state file and phase artifact files. The state file is the single source of truth for phase tracking and recovery.

**Rationale**: Modeled after Comet's `.comet.yaml`. AI reads one file (~200 bytes) and knows: skill name, target, current phase, all phase statuses, artifact paths, and result. No need to re-read SKILL.md, trace execution logs, or parse artifacts. This is the "fast resume" primitive.

```
.datamind/skill-sessions/2026-06-15-sales-cleaning/
├── .skill.yaml          # phase: execute, status: in_progress
├── phase-1-analyze.md   # Analysis output
├── phase-2-strategy.md  # Proposed strategy
├── phase-3-gate.json    # Gate approval record
└── phase-4-execution.json
```

### D4: Prompt Templates — Directory of markdown files

**Decision**: System prompt templates live in a directory as `.md` files with YAML frontmatter for metadata. Templates support `{{ variable }}` injection for context, skills list, datasets, and parameters.

**Rationale**: Markdown is AI-native (both human and LLM readable). Directory structure allows adding/removing templates without code changes. YAML frontmatter provides machine-readable metadata without parsing complexity.

```
prompts/
├── data-scientist.md    # Default: full data science context
├── code-reviewer.md     # Review generated scripts
├── requirement-analyst.md  # requirement-discussion skill
└── archivist.md         # auto-archive skill
```

### D5: Usage Tracking — Per-session aggregation

```

Full source: openspec/changes/datamind-engine-v2/design.md

## openspec/changes/datamind-engine-v2/tasks.md

- Source: openspec/changes/datamind-engine-v2/tasks.md
- Lines: 1-60
- SHA256: be917e8cafd6601d50e473a963a78c897117212e7add917d7a2232e940e75aac

```md
# Tasks: datamind-engine-v2

## Phase 1: LLM Foundation

- [ ] **T1.1** — Implement `engine/llm.py`: `BaseLLMClient` abstract class, `OpenAIClient`, `OllamaClient` with chat completion, streaming, tool calling, retry (3x exponential backoff)
- [ ] **T1.2** — Extend `config.py` with LLM configuration: providers list, model definitions, `${ENV_VAR}` resolution, merge env vars with file config
- [ ] **T1.3** — Implement Ollama model auto-discovery: run `ollama list`, parse output, cache with TTL, fallback to manual config
- [ ] **T1.4** — Write tests for LLM client (mocked API responses, retry logic, streaming, env var resolution, Ollama list parsing)

## Phase 2: Prompt & Usage

- [ ] **T2.1** — Implement `engine/prompt.py`: `TemplateManager` loading markdown files from directory, YAML frontmatter parsing, `{{ variable }}` injection
- [ ] **T2.2** — Create 4 prompt templates: `data-scientist.md`, `code-reviewer.md`, `requirement-analyst.md`, `archivist.md`
- [ ] **T2.3** — Implement `engine/usage.py`: `UsageTracker` with per-session token counting, cost calculation, usage export
- [ ] **T2.4** — Write tests for prompt manager and usage tracker

## Phase 3: Skill State Machine

- [ ] **T3.1** — Implement `engine/skill_state.py`: `SkillStateMachine` with phase tracking, transition validation, `.skill.yaml` read/write
- [ ] **T3.2** — Implement `SkillSession` in `engine/skills.py`: session directory creation, artifact tracking, result recording
- [ ] **T3.3** — Rewrite `SkillParser` to support extended SKILL.md format with phase definitions
- [ ] **T3.4** — Write tests for state machine (transitions, validation, serialization, recovery)

## Phase 4: Agent Loop

- [ ] **T4.1** — Implement `engine/agent.py`: `DataMindAgent` loop (assemble context → render prompt → LLM call → execute tools → record decisions)
- [ ] **T4.2** — Implement GATE handling: pause execution, yield `WaitForApproval`, resume on human input
- [ ] **T4.3** — Implement tool definitions: bridge skills as LLM function calls, execute and return results
- [ ] **T4.4** — Write integration tests for agent loop (mock LLM, verify context assembly, tool execution, gate pause/resume)

## Phase 5: Skills Rewrite

- [ ] **T5.1** — Rewrite `skills/data-cleaning.md` with phase-based definition
- [ ] **T5.2** — Rewrite `skills/data-exploration.md` with phase-based definition
- [ ] **T5.3** — Rewrite `skills/feature-engineering.md` with phase-based definition
- [ ] **T5.4** — Rewrite `skills/model-training.md` with phase-based definition
- [ ] **T5.5** — Rewrite `skills/report-generation.md` with phase-based definition
- [ ] **T5.6** — Create `skills/requirement-discussion.md` (explore-context → propose-frame → gate-review → define-success → scope-analysis → gate-confirm)
- [ ] **T5.7** — Create `skills/auto-archive.md` (audit-artifacts → generate-summary → organize-outputs → gate-review-plan → execute-archive)

## Phase 6: L1-L3 Extensions

- [ ] **T6.1** — Implement materialized view rebuild in `engine/events.py`: read `executions/`, reconstruct dataset state
- [ ] **T6.2** — Implement reproducibility in `engine/lineage.py`: trace lineage to raw ancestors, replay script chain in order
- [ ] **T6.3** — Implement auto-refresh in `engine/assembly.py`: regenerate context files on state change triggers (dataset added, decision logged, execution completed)
- [ ] **T6.4** — Write tests for materialized view, reproducibility, and auto-refresh

## Phase 7: API & Integration

- [ ] **T7.1** — Add SSE chat endpoint to `api/app.py`: streaming chat with agent loop, tool call progress events
- [ ] **T7.2** — Add model listing and switching endpoints
- [ ] **T7.3** — Add usage/cost query endpoint
- [ ] **T7.4** — Update CLI `chat` command to use agent loop with streaming
- [ ] **T7.5** — Update MCP server tools to integrate agent loop where applicable

## Phase 8: End-to-End Validation

- [ ] **T8.1** — E2E test: full skill execution (data-cleaning) through all phases including gate pause/resume
- [ ] **T8.2** — E2E test: interrupt/resume recovery — simulate context loss, verify AI can read `.skill.yaml` and continue
- [ ] **T8.3** — Run full test suite, ensure 100% pass rate
```

## openspec/changes/datamind-engine-v2/specs/agent-execution/spec.md

- Source: openspec/changes/datamind-engine-v2/specs/agent-execution/spec.md
- Lines: 1-70
- SHA256: 753298d47e315167a460b5540d2a44ba9956116ca21b34b076cd23560e28c0f3

```md
﻿# agent-execution Specification

## Purpose
Agent execution loop that orchestrates context assembly, prompt rendering, LLM calls, tool execution, and decision recording. Includes the skill session state machine for interrupt/resume.

## ADDED Requirements

### Requirement: Agent Loop
The system SHALL provide an agent loop that executes: assemble context → render system prompt → call LLM with tools → execute tool calls → record decisions → repeat. The loop SHALL continue until the task completes or a GATE step requires human input.

#### Scenario: Agent executes AUTO step
- **WHEN** the current skill step is AUTO
- **THEN** the agent assembles context, renders the prompt, calls the LLM, executes any tool calls, records the result, and advances to the next step

#### Scenario: Agent pauses at GATE step
- **WHEN** the current skill step is GATE
- **THEN** the agent pauses execution and yields a `WaitForApproval` response with the proposal content, waiting for human input (APPROVE/REJECT/MODIFY)

#### Scenario: Agent resumes after gate
- **WHEN** human provides approval at a GATE step
- **THEN** the agent records the gate decision and advances to the next AUTO step

#### Scenario: Tool execution
- **WHEN** the LLM returns a tool call (e.g., `read_describe`, `execute_script`)
- **THEN** the agent executes the tool with provided arguments and returns the result to the LLM for the next turn

### Requirement: Skill State Machine
The system SHALL manage skill execution through a `SkillStateMachine` that tracks phases, validates transitions, and persists state to `.skill.yaml`. Each skill invocation SHALL create a timestamped session directory under `.datamind/skill-sessions/`.

#### Scenario: Session initialization
- **WHEN** a skill is invoked with `/skill data-cleaning sales.csv`
- **THEN** a session directory is created at `.datamind/skill-sessions/<timestamp>-sales-cleaning/` containing `.skill.yaml` with `phase: analyze` and all phase statuses `pending`

#### Scenario: Phase transition
- **WHEN** the analyze phase completes successfully
- **THEN** `.skill.yaml` updates to `phase: propose-strategy`, with `analyze: complete` and the artifact path recorded

#### Scenario: Phase transition validation
- **WHEN** code attempts to advance to `execute` while `gate-approve` is still `awaiting_human`
- **THEN** the state machine rejects the transition with an error

### Requirement: Interrupt and Resume
The system SHALL support interrupting skill execution at any point and resuming from the exact phase without re-executing completed steps. AI SHALL be able to read `.skill.yaml` and understand: current phase, completed phases, artifact locations, and what the next step requires.

#### Scenario: Resume after interruption
- **WHEN** a skill session was interrupted during `execute` phase
- **THEN** reading `.skill.yaml` shows `phase: execute`, `propose-strategy: complete` with artifact path `phase-2-strategy.md`
- **THEN** AI reads `phase-2-strategy.md` to understand the approved strategy and continues from `execute`

#### Scenario: Fast context recovery
- **WHEN** AI context was lost and needs to resume a skill session
- **THEN** AI reads `.skill.yaml` (~200 bytes) and knows the exact phase, completed phases, artifact paths, and pending statuses — without re-reading SKILL.md or execution logs

### Requirement: Skill Session Artifact Tracking
The system SHALL track all phase artifacts in `.skill.yaml` under an `artifacts` map. Each completed phase SHALL record the path to its output artifact. The result field SHALL be set to `pass` or `fail` upon skill completion.

#### Scenario: Artifact recording
- **WHEN** the `analyze` phase generates an analysis output
- **THEN** `.skill.yaml` records `artifacts.analyze: phase-1-analyze.md`

#### Scenario: Final result
- **WHEN** all phases complete successfully
- **THEN** `.skill.yaml` records `result: pass` and `completed_at: <timestamp>`

### Requirement: Framework-Agnostic Design
The LLM client layer (`engine/llm.py`) SHALL expose a framework-agnostic interface. The agent loop (`engine/agent.py`) SHALL be replaceable without modifying the LLM client, prompt manager, or usage tracker. This SHALL reserve a migration path to LangGraph for v3.

#### Scenario: Client independence
- **WHEN** `engine/agent.py` is replaced with a LangGraph-based implementation in v3
- **THEN** `engine/llm.py`, `engine/prompt.py`, and `engine/usage.py` require zero changes
```

## openspec/changes/datamind-engine-v2/specs/context-assembly/spec.md

- Source: openspec/changes/datamind-engine-v2/specs/context-assembly/spec.md
- Lines: 1-21
- SHA256: 618aeb74033becd984205021449fcf8ca69286bfd4ca802a642b6f87f40ace53

```md
﻿# context-assembly Delta Specification

## Purpose
Add automatic context file refresh triggered by project state changes.

## ADDED Requirements

### Requirement: Context File Auto-Refresh
The system SHALL regenerate all context files (PROJECT.md, DATASETS.md, HISTORY.md, EXPLORATION.md, PARAMS.md) after every AI execution that changes project state. Regeneration SHALL be triggered by: dataset registration, script execution, decision logging, discovery recording, and parameter updates.

#### Scenario: Dataset added triggers refresh
- **WHEN** a new dataset is uploaded or created
- **THEN** DATASETS.md is regenerated to include the new dataset schema and metadata

#### Scenario: Decision logged triggers refresh
- **WHEN** a new decision is recorded in decisions.jsonl
- **THEN** HISTORY.md is regenerated to include the new decision entry

#### Scenario: Batch refresh after multi-step execution
- **WHEN** a skill execution changes multiple state layers (lineage + cognition + assembly)
- **THEN** all affected context files are refreshed once after the execution completes, not after each individual change
```

## openspec/changes/datamind-engine-v2/specs/data-lineage/spec.md

- Source: openspec/changes/datamind-engine-v2/specs/data-lineage/spec.md
- Lines: 1-28
- SHA256: 7ee44b8774892ada9a9157577231cf6ff3bc0396cb524c9ad630d03535b11e4a

```md
﻿# data-lineage Delta Specification

## Purpose
Add reproducibility execution and materialized view rebuild to the data lineage capability.

## ADDED Requirements

### Requirement: Materialized View Rebuild
The system SHALL provide a mechanism to rebuild the current dataset state by reading execution logs from `executions/` in chronological order and replaying each recorded operation against the graph database. This SHALL complete the event sourcing read path.

#### Scenario: Rebuild from execution logs
- **WHEN** the materialized view is stale or corrupted
- **THEN** reading `executions/` in timestamp order and replaying each operation reconstructs the full dataset state in graph.db

#### Scenario: Rebuild with monotonic timestamps
- **WHEN** replaying execution logs to rebuild state
- **THEN** events are applied in monotonic counter order, ensuring deterministic reconstruction

### Requirement: Reproducibility
The system SHALL enable reproducing any processed dataset by tracing its lineage back to raw data ancestors and re-running the script chain in dependency order.

#### Scenario: Reproduce processed dataset
- **WHEN** user requests to reproduce `data/processed/sales_agg.parquet`
- **THEN** the system traces lineage back to `data/raw/sales.csv` and re-runs `clean_nulls.py` then `aggregate.py` in order

#### Scenario: Reproduce with multi-parent dataset
- **WHEN** user requests to reproduce a dataset created by merging two parents
- **THEN** the system traces both parent lineages back to raw data and re-runs all scripts in topological order
```

## openspec/changes/datamind-engine-v2/specs/llm-integration/spec.md

- Source: openspec/changes/datamind-engine-v2/specs/llm-integration/spec.md
- Lines: 1-92
- SHA256: cdf57b3f1ff5d4f98a0fae4e7baadb7a90ef7b38b6291868fac0d5286ee10c51

[TRUNCATED]

```md
﻿# llm-integration Specification

## Purpose
LLM client abstraction layer supporting OpenAI-compatible APIs and Ollama local models, with multi-model switching, prompt template management, and usage tracking.

## ADDED Requirements

### Requirement: LLM Client Abstraction
The system SHALL provide a unified LLM client interface (`BaseLLMClient`) with concrete implementations for OpenAI-compatible APIs (`OpenAIClient`) and Ollama local models (`OllamaClient`). All clients SHALL support chat completion, streaming responses, and tool calling through a common interface.

#### Scenario: OpenAI chat completion
- **WHEN** agent calls `llm.chat(messages=[...], tools=[...])` with provider configured as `openai`
- **THEN** the request is sent to the configured OpenAI-compatible endpoint and the response is returned with text content and any tool calls

#### Scenario: Ollama chat completion
- **WHEN** agent calls `llm.chat(messages=[...])` with provider configured as `ollama`
- **THEN** the request is sent to the local Ollama endpoint (`http://localhost:11434/v1`) and the response is returned

#### Scenario: Streaming response
- **WHEN** agent calls `llm.chat(messages=[...], stream=True)`
- **THEN** the method yields response chunks as they arrive, enabling real-time display

#### Scenario: API error retry
- **WHEN** an API call fails with a transient error (429, 502, 503)
- **THEN** the client retries up to 3 times with exponential backoff before raising an error

### Requirement: Multi-Model Switching
The system SHALL support switching between configured LLM models at runtime without restarting. The active model SHALL be specifiable per request or per session.

#### Scenario: Runtime model switch
- **WHEN** user selects a different model from the configured list
- **THEN** subsequent LLM calls use the newly selected model immediately

#### Scenario: Per-request model override
- **WHEN** agent specifies `model="deepseek-v3"` in a chat call
- **THEN** that single request uses deepseek-v3 regardless of the session default model

### Requirement: Ollama Model Auto-Discovery
When the Ollama provider is configured, the system SHALL automatically discover available models by running `ollama list`. The discovered model list SHALL be cached with a configurable TTL.

#### Scenario: Auto-discover models
- **WHEN** the system starts with Ollama provider enabled and `ollama list` returns models
- **THEN** the model list is populated from the command output and available for selection

#### Scenario: Ollama unavailable fallback
- **WHEN** `ollama list` fails (Ollama not installed or not running)
- **THEN** the system falls back to manually configured model names in `config.yaml`

### Requirement: LLM Configuration
The system SHALL load LLM configuration from `.datamind/config.yaml` with support for `${ENV_VAR}` environment variable injection. Environment variables SHALL take precedence over file values.

#### Scenario: Config with env var
- **WHEN** config contains `api_key: ${OPENAI_API_KEY}` and the environment variable is set
- **THEN** the resolved value uses the environment variable

#### Scenario: Config file only
- **WHEN** config contains a plain value like `api_url: https://api.openai.com/v1`
- **THEN** the value is used as-is from the config file

#### Scenario: Env var override
- **WHEN** both config file and environment variable specify the same key
- **THEN** the environment variable value takes precedence

### Requirement: System Prompt Templates
The system SHALL load system prompt templates from a directory as markdown files with YAML frontmatter metadata. Templates SHALL support `{{ variable }}` injection for dynamic content including context manifest, skills list, datasets, and parameters.

#### Scenario: Load template
- **WHEN** agent requests the `data-scientist` template
- **THEN** the system reads `prompts/data-scientist.md`, parses YAML frontmatter, and returns the template with metadata

#### Scenario: Variable injection
- **WHEN** template contains `{{ context }}` and context manifest is provided
- **THEN** the rendered output replaces `{{ context }}` with the assembled context manifest content

#### Scenario: Missing template fallback
- **WHEN** requested template file does not exist
- **THEN** the system falls back to a built-in default system prompt

### Requirement: Usage Tracking
The system SHALL track token usage and cost for every LLM call, aggregated per skill session. Cost rates SHALL be configurable per model in `config.yaml`. Ollama local models SHALL track tokens with zero cost.
```

Full source: openspec/changes/datamind-engine-v2/specs/llm-integration/spec.md

## openspec/changes/datamind-engine-v2/specs/skill-system/spec.md

- Source: openspec/changes/datamind-engine-v2/specs/skill-system/spec.md
- Lines: 1-70
- SHA256: 991f19265d871a5d46d6ac8cd1924f2a9a26719d33cf74708814f999b3e67bc0

```md
﻿# skill-system Delta Specification

## Purpose
Replace the parse-only v1 SkillService with a full SkillSession state machine supporting phase tracking, artifact management, and interrupt/resume recovery. Rewrite all 7 skills with Comet-style phase definitions.

## ADDED Requirements

### Requirement: Skill Session State Machine
The system SHALL manage skill execution through a `SkillStateMachine` that persists execution state to `.skill.yaml` in a timestamped session directory. The state file SHALL be the single source of truth for phase tracking and recovery. Each skill invocation SHALL create an isolated session directory under `.datamind/skill-sessions/`.

#### Scenario: Session lifecycle
- **WHEN** a skill is invoked
- **THEN** `.skill.yaml` is initialized with all phases `pending`, the first phase set as active, and session metadata recorded (skill name, target, started_at)

#### Scenario: Phase advancement
- **WHEN** a phase completes
- **THEN** the state machine validates the transition, records the phase output artifact path, and advances to the next phase

#### Scenario: Invalid transition rejected
- **WHEN** code attempts to skip a GATE phase or advance out of sequence
- **THEN** the state machine rejects the transition with a descriptive error

### Requirement: Interrupt and Resume Recovery
Every skill session SHALL support interruption and resumption without data loss. An AI reading `.skill.yaml` SHALL be able to determine: current phase, all completed phase statuses, artifact locations, and pending phases — without re-reading the SKILL.md definition or execution logs.

#### Scenario: Context loss recovery
- **WHEN** AI context is lost mid-execution and the AI reads `.skill.yaml`
- **THEN** the AI sees `phase: execute`, `analyze: complete` with artifact `phase-1-analyze.md`, `propose-strategy: complete` with artifact `phase-2-strategy.md`, `gate-approve: complete` with artifact `phase-3-gate.json`, and continues from `execute` using the recorded artifacts

#### Scenario: Disk-persistent state
- **WHEN** the process terminates unexpectedly during skill execution
- **THEN** `.skill.yaml` remains on disk with all completed phase data intact, ready for the next AI session to resume

### Requirement: Phase-Based Skill Definitions
All SKILL.md files SHALL define workflow steps as named phases. Each phase SHALL have a unique identifier, type (AUTO or GATE), and description. The `SkillParser` SHALL extract phases into a structured definition usable by the state machine.

#### Scenario: Parse phase-based skill
- **WHEN** a SKILL.md defines `1. Analyze (AUTO) — Read describe output`
- **THEN** the parser extracts phase `id: analyze`, `type: AUTO`, `description: Read describe output`

#### Scenario: Validate skill phases
- **WHEN** a SKILL.md is loaded
- **THEN** the parser validates that all phase IDs are unique, at least one phase exists, and no GATE phase is the final phase

## MODIFIED Requirements

### Requirement: Skill Definition Format
The system SHALL support skills defined as markdown files (SKILL.md) containing: purpose, required inputs, workflow phases (each tagged AUTO or GATE), and expected outputs. Each phase SHALL have a unique identifier, a type tag, and a description. The skill definition SHALL be parseable into a structured format suitable for state machine initialization.

#### Scenario: Define a phase-based skill
- **WHEN** the system loads the data-cleaning skill
- **THEN** it reads SKILL.md and extracts phases: Analyze (AUTO) → Propose Strategy (AUTO) → Gate: Approve Strategy (GATE) → Execute (AUTO) → Validate (AUTO) → Gate: Approve Result (GATE)

#### Scenario: Define a custom skill
- **WHEN** a user creates `skills/fintech-sentiment/SKILL.md`
- **THEN** the skill is registered and available for invocation alongside built-in skills

### Requirement: Skill Invocation
The system SHALL allow users to invoke skills via the chat interface using a `/skill <name> <args>` command syntax. Invocation SHALL create a timestamped session directory under `.datamind/skill-sessions/` and initialize a `.skill.yaml` state file. The skill SHALL read project context from the context manifest before executing.

#### Scenario: Invoke data-cleaning skill
- **WHEN** user types `/skill data-cleaning sales.csv` in the chat
- **THEN** the session directory is created, `.skill.yaml` is initialized with phase `analyze`, and the data-cleaning skill begins execution reading context from the context manifest

### Requirement: Skill Execution Context
Every skill execution SHALL read from the context manifest, write to the appropriate storage layers (graph.db, decisions.jsonl, exploration.json, params.json, discoveries.jsonl), generate an execution log, and track state in `.skill.yaml`. After execution completes, context files SHALL be auto-refreshed.

#### Scenario: Skill writes to all layers with state tracking
- **WHEN** the model-training skill completes
- **THEN** the new model is registered in graph.db, hyperparameters are written to params.json, model comparison results are written to exploration.json, an execution log is saved, and `.skill.yaml` records `result: pass` with all phase artifacts tracked
```

