# agent-execution Specification

## Purpose
TBD - created by archiving change datamind-engine-v2. Update Purpose after archive.
## Requirements
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

