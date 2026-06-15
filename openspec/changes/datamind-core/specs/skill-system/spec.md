## ADDED Requirements

### Requirement: Skill Definition Format
The system SHALL support skills defined as markdown files (SKILL.md) containing: purpose, required inputs, workflow steps, and expected outputs. Each workflow step SHALL be tagged as AUTO (AI executes autonomously) or GATE (requires human approval).

#### Scenario: Define a built-in skill
- **WHEN** the system loads the data-cleaning skill
- **THEN** it reads SKILL.md containing: Analyze (AUTO) → Propose Strategy (AUTO) → Gate: Approve Strategy (GATE) → Execute (AUTO) → Validate (AUTO) → Gate: Approve Result (GATE)

#### Scenario: Define a custom skill
- **WHEN** a user creates `skills/fintech-sentiment/SKILL.md`
- **THEN** the skill is registered and available for invocation alongside built-in skills

### Requirement: Skill Invocation
The system SHALL allow users to invoke skills via the chat interface using a `/skill <name> <args>` command syntax. The skill SHALL read project context from the context manifest before executing.

#### Scenario: Invoke data-cleaning skill
- **WHEN** user types `/skill data-cleaning sales.csv` in the chat
- **THEN** the data-cleaning skill is invoked with `sales.csv` as the target dataset, reading its description from `describe/sales.csv.describe.md`

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
Every skill execution SHALL read from the context manifest, write to the appropriate storage layers (graph.db, decisions.jsonl, exploration.json, params.json, discoveries.jsonl), and generate an execution log.

#### Scenario: Skill writes to all layers
- **WHEN** the model-training skill completes
- **THEN** the new model is registered in graph.db, hyperparameters are written to params.json, model comparison results are written to exploration.json, and an execution log is saved
