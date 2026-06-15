# agent-execution Specification

## Purpose
TBD - created by archiving change datamind-engine-v2. Update Purpose after archive.
## Requirements
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

