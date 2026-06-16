## ADDED Requirements

## ADDED Requirements

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
