# skill-system Specification

## Purpose
TBD - created by archiving change datamind-core. Update Purpose after archive.
## Requirements
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

### Requirement: Gate Approval
The system SHALL pause execution at GATE steps and present the human with the AI's proposal. The human SHALL be able to APPROVE, REJECT, or MODIFY the proposal.

#### Scenario: Human approves at gate
- **WHEN** AI presents a cleaning strategy and the human clicks APPROVE
- **THEN** the skill proceeds to the Execute step

#### Scenario: Human modifies at gate
- **WHEN** AI presents a feature set and the human says "APPROVE but drop day_of_week, add sentiment_ma_7d"
- **THEN** the AI adjusts the proposal accordingly and proceeds to Execute

#### Scenario: Human rejects at gate
- **WHEN** AI presents a model choice and the human clicks REJECT with feedback
- **THEN** the AI returns to the Propose step with the feedback incorporated

### Requirement: Skill Pipeline Composition
The system SHALL support chaining skills into pipelines where the outputs of one skill become the inputs of the next. The pipeline SHALL maintain context across skill boundaries.

#### Scenario: End-to-end project pipeline
- **WHEN** user runs the pipeline `data-cleaning → feature-engineering → model-training → report-generation`
- **THEN** each skill reads the outputs of the previous skill, and the context manifest is updated between each step

### Requirement: Skill Execution Context
Every skill execution SHALL read from the context manifest, write to the appropriate storage layers (graph.db, decisions.jsonl, exploration.json, params.json, discoveries.jsonl), generate an execution log, and track state in `.skill.yaml`. After execution completes, context files SHALL be auto-refreshed.

#### Scenario: Skill writes to all layers with state tracking
- **WHEN** the model-training skill completes
- **THEN** the new model is registered in graph.db, hyperparameters are written to params.json, model comparison results are written to exploration.json, an execution log is saved, and `.skill.yaml` records `result: pass` with all phase artifacts tracked

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

