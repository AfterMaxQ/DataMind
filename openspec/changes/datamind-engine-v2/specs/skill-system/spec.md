# skill-system Delta Specification

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
