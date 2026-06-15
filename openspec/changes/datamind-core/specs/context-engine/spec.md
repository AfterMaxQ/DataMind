## ADDED Requirements

### Requirement: Project Initialization
The system SHALL initialize a `.datamind/` directory in any project folder with the standard structure: `graph.db` (SQLite knowledge graph), `context/` (generated context files), `config.yaml` (project configuration).

#### Scenario: Initialize new project
- **WHEN** user runs project initialization on an empty or existing project directory
- **THEN** the `.datamind/` directory is created with graph.db, context/ subdirectory, and config.yaml

#### Scenario: Re-initialize existing project
- **WHEN** user initializes a project that already has a `.datamind/` directory
- **THEN** the system detects existing structure and offers to repair or reinitialize without data loss

### Requirement: Event Logging
The system SHALL record every AI action as an immutable event in `executions/` directory. Each event file SHALL be a self-contained markdown document with timestamp, task description, AI reasoning, generated code, outputs, and links to affected datasets.

#### Scenario: AI completes a task
- **WHEN** AI finishes executing a skill step or ad-hoc request
- **THEN** an execution log file is written to `executions/<timestamp>_<task>.md` with full details

#### Scenario: Read execution history
- **WHEN** the system needs to reconstruct project activity
- **THEN** execution logs can be read in chronological order from the `executions/` directory

### Requirement: Knowledge Graph Storage
The system SHALL store typed nodes (Dataset, Script, Execution, Decision, Finding, Checkpoint) and typed edges (GENERATED_BY, PRODUCED, USED_INPUT, TRIGGERED, DISCOVERED_DURING) in a SQLite database at `graph.db`.

#### Scenario: Add a dataset node
- **WHEN** a new dataset is uploaded or created
- **THEN** a Dataset node is inserted into graph.db with metadata (name, path, type, row count, column count)

#### Scenario: Query lineage
- **WHEN** the system needs to find all ancestors of a dataset
- **THEN** recursive graph traversal returns the full chain of datasets and scripts that produced it

#### Scenario: Query descendants
- **WHEN** the system needs to find all datasets derived from a raw dataset
- **THEN** recursive graph traversal returns all downstream datasets and the scripts that created them

### Requirement: Project Directory Format
The system SHALL define and enforce the standard DataMind project structure: `data/raw/` for immutable originals, `data/processed/` for derived datasets, `scripts/` for AI-generated code, `describe/` for auto-generated data descriptions, and `executions/` for event logs.

#### Scenario: Upload raw dataset
- **WHEN** user drags a CSV file into the data sidebar
- **THEN** the file is placed in `data/raw/` and a Dataset node is created in graph.db
