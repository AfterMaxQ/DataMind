# Comet Design Handoff

- Change: datamind-core
- Phase: design
- Mode: compact
- Context hash: b39985f46a0970c5e1ba6aaa2567fafc207239e0d8f8f915706cd1f3a444ba69

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/datamind-core/proposal.md

- Source: openspec/changes/datamind-core/proposal.md
- Lines: 1-35
- SHA256: 70cf5f3d2ff9517479598e03eac423a62599d298802543639cc60cc4994575f3

```md
## Why

AI agents in data science suffer from **session amnesia**. Every new conversation window resets the AI's understanding of the project — what data exists, how it was processed, why certain decisions were made, which approaches were tried and failed. Data scientists spend significant time re-explaining project context instead of doing actual work. This problem is acute because data science is inherently cumulative: each cleaning step, each exploration, each failed model attempt builds understanding that future work depends on.

Existing tools track artifacts (DVC tracks data versions, MLflow tracks experiments, Jupyter notebooks capture code) but **none capture the full cognitive journey** — the decisions, the dead ends, the parameters, the accidental discoveries — in a structured format that AI agents can consume across sessions.

## What Changes

- **Data lineage engine**: Automatic tracking of raw → processed data transformations. Scripts serve as edges between dataset nodes. Every dataset gets an auto-generated description (schema, statistics, distributions) so AI never needs to re-read raw files.
- **Cognitive journey capture**: Structured logging of decisions (what, why, alternatives, implications), exploration trees (including dead ends), parameter snapshots (normalization bounds, split dates, hyperparameters), and discovery feed (accidental insights, structured chronologically).
- **Context assembly & injection**: Priority-ordered, token-budget-aware context manifest assembled from lineage + cognition layers. Injected at the start of every AI session so the AI immediately understands the project.
- **Skill orchestration system**: Encoded data science workflows (data-cleaning, feature-engineering, model-training, report-generation) with human approval gates. Skills read project context, execute within a defined structure, and write results back to all layers. Humans only appear at decision gates — judgment, not labor.
- **Three-panel web interface**: Data sidebar (raw/processed browsing with lineage links), central dialogue panel (skill invocation, AI interaction, code display), right context panel (live lineage graph, recent decisions, active parameters).

## Capabilities

### New Capabilities

- `context-engine`: Core knowledge graph and event store. Manages the SQLite-based graph database, event sourcing for all AI actions, and the structured project directory format (`.datamind/`).
- `data-lineage`: Data lineage tracking with script-as-edge pattern. Auto-generates data descriptions for every dataset. Tracks raw → processed relationships through processing scripts.
- `cognitive-journey`: Decision log, exploration tree, parameter registry, and discovery feed. Captures the WHY and LEARNED alongside the WHAT.
- `context-assembly`: Priority-ordered context packer that generates context manifest files (PROJECT.md, DATASETS.md, HISTORY.md, CHECKPOINT.md) for AI session injection.
- `skill-system`: Skill definitions with structured workflows (analyze → propose → gate → execute → validate → gate). Built-in skills for common data science tasks. Custom skill creation support. Skill pipeline composition.
- `web-ui`: Three-panel web application (sidebar, chat, context panel) for interacting with the system. Drag-drop dataset upload, skill invocation, code display, and live lineage visualization.

### Modified Capabilities

<!-- No existing capabilities to modify — this is a greenfield project. -->

## Impact

- **New project**: Greenfield development. No existing code to modify.
- **Tech stack (proposed)**: Python backend (FastAPI or similar), SQLite for graph storage, Vue for web UI, MCP integration for Claude Code interoperability.
- **Dependencies**: None on existing systems. Will define `.datamind/` as a portable project format.
- **Deployment**: Local-first (runs alongside the user's tools). Web UI served locally.
```

## openspec/changes/datamind-core/design.md

- Source: openspec/changes/datamind-core/design.md
- Lines: 1-111
- SHA256: f6b18b7260dd63fa60118de785ddf0b7c4831a62d9429ee72aa97dbb29bf4f90

[TRUNCATED]

```md
## Context

DataMind Studio is a greenfield project. No existing code or architecture to integrate with. The system addresses AI session amnesia in data science workflows — the problem that every new AI conversation starts with zero knowledge of the project's data, history, decisions, and discoveries.

The target users are data scientists and analysts who use AI tools (Claude Code, ChatGPT, etc.) alongside their data work. They need a system that:
- Automatically captures project context without manual effort
- Injects relevant context into new AI sessions
- Supports both AI-driven and manual data workflows
- Works locally (no cloud dependency required)

## Goals / Non-Goals

**Goals:**
- Define a portable project format (`.datamind/`) that captures data lineage and cognitive journey
- Provide automatic context injection for AI sessions
- Enable skill-based workflow orchestration with human approval gates
- Deliver a three-panel web UI for browsing data, chatting with AI, and viewing context

**Non-Goals:**
- Cloud-hosted collaboration (v1 is single-user, local-first)
- Real-time multiplayer editing
- Replacement for Jupyter/VSCode (DataMind complements existing tools)
- Data storage/warehousing (DataMind references data, doesn't host it)
- Model serving or deployment

## Decisions

### Decision 1: Four-Layer Architecture

**Chosen**: L1 Lineage → L2 Cognition → L3 Assembly → L4 Skills

Layer 1 tracks WHAT happened to data (graph, scripts, descriptions). Layer 2 tracks WHY and what was learned (decisions, explorations, params, discoveries). Layer 3 assembles curated context from both layers for AI injection. Layer 4 orchestrates skills that read from and write to all lower layers.

**Alternatives considered**:
- **Monolithic context store**: Simpler but conflates data tracking with decision tracking. Harder to evolve independently.
- **Plugin architecture**: Too flexible for v1. Adds complexity without clear benefit.

**Rationale**: The separation between "what happened to data" and "why it happened" emerged from walking through a real financial analyst workflow. Data lineage tools exist (DVC) and experiment trackers exist (MLflow), but none connect them. The four layers are not arbitrary — each one solves a distinct problem discovered in the analyst journey.

### Decision 2: SQLite for Knowledge Graph Storage

**Chosen**: SQLite with a relational schema representing typed nodes and edges. Not a dedicated graph database (Neo4j, ArangoDB), not a vector database.

**Rationale**:
- SQLite is embedded, zero-config, works offline — matches local-first deployment
- Data lineage is inherently relational (datasets, scripts, executions, parameters all have structured schemas)
- Graph queries (find ancestors, descendants) can be expressed as recursive CTEs in SQL
- Vector search is not needed for this use case (decisions and discoveries are tagged and structured, not semantically searched)
- Single file (graph.db) is portable alongside the project

### Decision 3: Script-as-Edge Pattern

**Chosen**: The processing script filename/ID serves as the edge between dataset nodes in the lineage graph. No separate mapping table.

Example: `scripts/clean_nulls.py` is the edge from `raw/sales.csv` to `processed/sales_clean.csv`.

**Alternatives considered**:
- **Separate edge table in graph.db**: More flexible but redundant — the script already uniquely identifies the transformation.
- **Content-hash based edges**: Content-addressable but fragile when scripts are modified.

**Rationale**: The script is the transformation. Making it the edge means reading the lineage graph immediately tells you which script to re-run to reproduce any dataset. This is the simplest solution that solves the problem.

### Decision 4: Event Sourcing as the Write Model

**Chosen**: Every AI action is written as an immutable event log entry first. The knowledge graph (graph.db), decisions.jsonl, params.json, etc. are materialized views rebuilt from the event log.

**Rationale**:
- Audit trail: every AI action is traceable
- Replay: can reconstruct project state from any point
- Resilience: if a materialized view gets corrupted, rebuild from events
- The execution log files (`executions/*.md`) are the event source, not a separate database

### Decision 5: Context Packing Algorithm (Priority-Ordered, Not Semantic Search)

**Chosen**: Context is assembled using priority tiers, not vector similarity search.

Priority tiers:
1. ALWAYS: PROJECT.md + all DATASETS.md
2. RECENT: last N decisions, executions, discoveries
3. RELEVANT: graph traversal for query-related nodes (tag-based, not embedding-based)
```

Full source: openspec/changes/datamind-core/design.md

## openspec/changes/datamind-core/tasks.md

- Source: openspec/changes/datamind-core/tasks.md
- Lines: 1-61
- SHA256: 561a9f079a5ed694f6acec02a7f2ea53a3058f3f0f4025ad0ae34c4d8a1d9f7f

```md
## 1. Project Scaffolding

- [ ] 1.1 Initialize Python project structure with FastAPI backend + Vue frontend
- [ ] 1.2 Define `.datamind/` directory schema and `config.yaml` format
- [ ] 1.3 Implement project initialization CLI (`datamind init`)

## 2. Context Engine (Layer 1 Foundation)

- [ ] 2.1 Design SQLite schema for typed nodes (Dataset, Script, Execution) and edges (GENERATED_BY, PRODUCED, USED_INPUT)
- [ ] 2.2 Implement graph database read/write API (insert node, insert edge, query ancestors, query descendants)
- [ ] 2.3 Implement event sourcing: write immutable execution logs to `executions/` directory
- [ ] 2.4 Implement materialized view rebuild from event log

## 3. Data Lineage (Layer 1)

- [ ] 3.1 Implement dataset registration: detect new files in `data/raw/` and `data/processed/`, create Dataset nodes
- [ ] 3.2 Implement auto-describe engine: read CSV/Parquet/Excel, infer types, compute statistics, generate `describe/*.md`
- [ ] 3.3 Implement script-as-edge pattern: parse script I/O to detect input/output datasets, link in graph
- [ ] 3.4 Implement lineage query API: trace ancestors (raw → ... → dataset) and descendants (dataset → ... → all outputs)
- [ ] 3.5 Implement reproducibility: re-run script chain from raw data to reproduce any processed dataset

## 4. Cognitive Journey (Layer 2)

- [ ] 4.1 Implement decision log (`decisions.jsonl`): structured entries with {id, what, why, alternatives, implications, timestamp}
- [ ] 4.2 Implement exploration tree (`exploration.json`): nodes with status tags (SELECTED, REJECTED, EXPLORATORY), parent-child relationships
- [ ] 4.3 Implement parameter registry (`params.json`): auto-extract parameters from scripts, key by script ID and execution run
- [ ] 4.4 Implement discovery feed (`discoveries.jsonl`): chronological entries with {timestamp, tag, finding, linked_code, linked_data}

## 5. Context Assembly (Layer 3)

- [ ] 5.1 Implement context file generator: produce PROJECT.md, DATASETS.md, HISTORY.md, EXPLORATION.md, PARAMS.md from lower layers
- [ ] 5.2 Implement priority-ordered context packer: assemble CONTEXT_MANIFEST.md with Priority 1-4 tiers
- [ ] 5.3 Implement token budget management: truncate/compress lower-priority content when budget exceeded
- [ ] 5.4 Implement checkpoint generator: periodically create CHECKPOINT.md (~2k tokens) summarizing project state
- [ ] 5.5 Implement auto-refresh: regenerate context files after every AI execution that changes state

## 6. Skill System (Layer 4)

- [ ] 6.1 Define SKILL.md format: purpose, inputs, workflow steps (AUTO | GATE), outputs
- [ ] 6.2 Implement skill loader: parse SKILL.md files from `skills/` directory
- [ ] 6.3 Implement skill executor: execute AUTO steps sequentially, pause at GATE steps
- [ ] 6.4 Implement gate approval flow: present proposal to human, accept APPROVE/REJECT/MODIFY
- [ ] 6.5 Create built-in skills: data-cleaning, data-exploration, feature-engineering, model-training, report-generation
- [ ] 6.6 Implement skill pipeline composer: chain skills where outputs of one become inputs of next
- [ ] 6.7 Implement custom skill creation: user-facing interface for defining new SKILL.md files

## 7. Web UI

- [ ] 7.1 Set up Vue project with three-panel layout (sidebar, center chat, right context panel)
- [ ] 7.2 Implement data sidebar: raw/processed folder tree, dataset metadata display, drag-and-drop upload
- [ ] 7.3 Implement chat panel: message display, `/skill` command parsing, code display with syntax highlighting
- [ ] 7.4 Implement gate interaction: APPROVE/REJECT/MODIFY buttons inline in chat
- [ ] 7.5 Implement context panel: live lineage graph visualization, recent decisions list, active parameters display
- [ ] 7.6 Implement session context indicator: show loaded context status, last session time, checkpoint version

## 8. Integration & Polish

- [ ] 8.1 Wire full pipeline: upload dataset → auto-describe → skill invocation → execution → context update → manifest refresh
- [ ] 8.2 Implement context injection for Claude Code MCP integration
- [ ] 8.3 Add project-level tests: end-to-end workflow from raw data to report
- [ ] 8.4 Documentation: user guide, skill authoring guide, project format specification
```

## openspec/changes/datamind-core/specs/cognitive-journey/spec.md

- Source: openspec/changes/datamind-core/specs/cognitive-journey/spec.md
- Lines: 1-53
- SHA256: e5628db25a93a6a658769c4ea574c7034dd75b627c73af966efcf4018f0ec892

```md
## ADDED Requirements

### Requirement: Decision Logging
The system SHALL capture every non-trivial decision made during the project as a structured entry containing: what was decided, why it was chosen, what alternatives were considered, and what downstream implications it has.

#### Scenario: AI proposes a decision
- **WHEN** AI proposes a cleaning strategy (e.g., "use forward fill for missing values")
- **THEN** a decision entry is created in `decisions.jsonl` with fields: {id, what, why, alternatives, implications, timestamp}

#### Scenario: Human overrides a decision
- **WHEN** human modifies or rejects an AI proposal at a gate
- **THEN** the decision log records the human's rationale alongside the AI's original proposal

#### Scenario: Query recent decisions
- **WHEN** a new AI session starts
- **THEN** the context assembly system reads the last N decisions from `decisions.jsonl` for injection

### Requirement: Exploration Tree
The system SHALL maintain a tree of all analytical approaches attempted, with each node tagged as SELECTED, REJECTED, or EXPLORATORY. Dead ends SHALL be preserved to prevent future AI sessions from repeating failed approaches.

#### Scenario: Record a failed model attempt
- **WHEN** the AI trains a logistic regression model that achieves only 52% accuracy
- **THEN** an EXPLORATORY node is created in `exploration.json`, later tagged REJECTED with reason "52% accuracy, below baseline"

#### Scenario: Record the selected approach
- **WHEN** the AI trains an XGBoost model that achieves 66% accuracy and is chosen for production
- **THEN** the XGBoost node is tagged SELECTED with the path from raw data through feature engineering

#### Scenario: New session reads exploration tree
- **WHEN** a new AI session starts and reads the exploration tree
- **THEN** the AI sees that logistic regression was already tried and rejected, and does not propose it again

### Requirement: Parameter Registry
The system SHALL automatically extract and register all parameters used in data processing and modeling, keyed to the script version and execution run. This SHALL include normalization bounds, train/test split dates, hyperparameters, and feature definitions.

#### Scenario: Script with hardcoded parameters runs
- **WHEN** a script executes with parameters like `split_date: 2025-01-01` and `norm_range: [0, 1]`
- **THEN** these parameters are extracted and stored in `params.json` with the script ID and run ID

#### Scenario: New session needs active parameters
- **WHEN** a new AI session starts and needs to continue model development
- **THEN** the context assembly includes all active parameters from `params.json`

### Requirement: Discovery Feed
The system SHALL provide a chronological feed for recording insights discovered during analysis, including unplanned discoveries. Each entry SHALL include a timestamp, tag, the finding itself, and links to the code and data that produced it.

#### Scenario: Accidental discovery during backtesting
- **WHEN** AI discovers that model accuracy drops 15% during earnings season
- **THEN** a discovery entry is created: {timestamp, tag: "model-weakness", finding: "Accuracy drops 15% during earnings season", linked_code: "scripts/backtest.py", linked_data: "processed/features.parquet"}

#### Scenario: Discovery feed informs future sessions
- **WHEN** a new AI session starts working on model improvement
- **THEN** the discovery "accuracy drops during earnings season" is injected, guiding the AI to address this known weakness
```

## openspec/changes/datamind-core/specs/context-assembly/spec.md

- Source: openspec/changes/datamind-core/specs/context-assembly/spec.md
- Lines: 1-44
- SHA256: 1c1a4ae77e5968bb4ca059e2a009eed4a50fc39eed329bf26eed91d1c6823507

```md
## ADDED Requirements

### Requirement: Context Manifest Generation
The system SHALL generate a CONTEXT_MANIFEST.md file that assembles curated project context from all layers (lineage, cognition) into a single AI-consumable document.

#### Scenario: New session context manifest
- **WHEN** a new AI session is about to start
- **THEN** CONTEXT_MANIFEST.md is generated containing: project overview, dataset registry summary, exploration tree active branch, recent decisions, active parameters, recent discoveries, and the latest checkpoint

### Requirement: Priority-Ordered Context Packing
The system SHALL assemble context using priority tiers: Priority 1 (ALWAYS) — PROJECT.md and all DATASETS.md; Priority 2 (RECENT) — last N decisions, executions, discoveries; Priority 3 (RELEVANT) — graph-traversed nodes related to the user's query; Priority 4 (COMPRESSED) — CHECKPOINT.md dense summary.

#### Scenario: Context pack respects priority order
- **WHEN** context is assembled for a token budget of 40k tokens
- **THEN** Priority 1 items are included first, then Priority 2, then Priority 3 and 4 as space allows

#### Scenario: Relevance-based inclusion
- **WHEN** user query mentions "revenue analysis"
- **THEN** the system traverses the graph for nodes tagged with "revenue" and includes them in Priority 3

### Requirement: Token Budget Awareness
The system SHALL target a configurable token budget when assembling context, truncating or compressing lower-priority content when the budget is exceeded.

#### Scenario: Large project exceeds token budget
- **WHEN** a project has 50 datasets and 200 decisions
- **THEN** all dataset schemas are still included (Priority 1), but older decisions are compressed to summaries and older execution logs are omitted

### Requirement: Checkpoint Generation
The system SHALL periodically generate a CHECKPOINT.md file that compresses all prior project activity into a dense, AI-consumable summary (target: ~2k tokens). The checkpoint SHALL include: active datasets, completed work, current task, open questions, and suggested next steps.

#### Scenario: Automatic checkpoint after significant activity
- **WHEN** 10 or more new execution logs have accumulated since the last checkpoint
- **THEN** the system generates a new CHECKPOINT.md summarizing the project state

#### Scenario: New session reads checkpoint
- **WHEN** a new AI session starts and there is a recent checkpoint
- **THEN** CHECKPOINT.md is included in the context manifest, giving the AI a dense understanding of project state

### Requirement: Context File Auto-Refresh
The system SHALL regenerate all context files (PROJECT.md, DATASETS.md, HISTORY.md, EXPLORATION.md, PARAMS.md) after every AI execution that changes project state.

#### Scenario: Dataset added triggers refresh
- **WHEN** a new dataset is uploaded or created
- **THEN** DATASETS.md is regenerated to include the new dataset's schema
```

## openspec/changes/datamind-core/specs/context-engine/spec.md

- Source: openspec/changes/datamind-core/specs/context-engine/spec.md
- Lines: 1-45
- SHA256: d7aa75ed18e89e2569e9604ffdd1482616e9cfbca7c1986b985f13d1df449fa6

```md
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
```

## openspec/changes/datamind-core/specs/data-lineage/spec.md

- Source: openspec/changes/datamind-core/specs/data-lineage/spec.md
- Lines: 1-41
- SHA256: 8d58c991ad584667756b33362499a6b09c818ebbce68e728b81346158106daca

```md
## ADDED Requirements

### Requirement: Auto-Generated Data Description
The system SHALL automatically generate a machine-readable description for every dataset when it is uploaded or created. The description SHALL include: row count, column count, file size, column names, inferred types, null percentages, unique value counts, and value ranges/distributions.

#### Scenario: CSV file uploaded
- **WHEN** a CSV file is added to `data/raw/`
- **THEN** a `describe/<filename>.describe.md` file is generated with schema, statistics, and column summaries

#### Scenario: Processed dataset created
- **WHEN** a script produces a new dataset in `data/processed/`
- **THEN** a description is auto-generated for the new dataset and saved to `describe/`

### Requirement: Script-as-Edge Lineage
The system SHALL treat each processing script as the relationship edge between its input and output datasets. The script filename and path SHALL uniquely identify the transformation. No separate edge table is required for data lineage.

#### Scenario: Script connects raw to processed
- **WHEN** AI generates and runs `scripts/clean_nulls.py` that reads `data/raw/sales.csv` and writes `data/processed/sales_clean.csv`
- **THEN** the lineage graph links `sales.csv` → `clean_nulls.py` → `sales_clean.csv`

#### Scenario: Multi-step lineage query
- **WHEN** user queries the lineage of `data/processed/sales_agg.parquet`
- **THEN** the system returns the full chain: `sales.csv` → `clean_nulls.py` → `sales_clean.csv` → `aggregate.py` → `sales_agg.parquet`

### Requirement: Dataset Registry
The system SHALL maintain a registry of all datasets with their location, type (raw or processed), parent datasets, generating script, and description reference.

#### Scenario: List all datasets
- **WHEN** the data sidebar loads
- **THEN** all datasets are displayed organized by raw/processed folders with lineage links visible

#### Scenario: Dataset with multiple parents
- **WHEN** a script merges two datasets (e.g., `merge.py` reads both `tweets_clean.csv` and `stock_clean.csv`)
- **THEN** the resulting dataset has two parent edges, both visible in the lineage graph

### Requirement: Reproducibility
The system SHALL enable reproducing any processed dataset by re-running the script chain from its raw data ancestors.

#### Scenario: Reproduce processed dataset
- **WHEN** user requests to reproduce `data/processed/sales_agg.parquet`
- **THEN** the system traces lineage back to `data/raw/sales.csv` and re-runs `clean_nulls.py` then `aggregate.py` in order
```

## openspec/changes/datamind-core/specs/skill-system/spec.md

- Source: openspec/changes/datamind-core/specs/skill-system/spec.md
- Lines: 1-48
- SHA256: 50b6a1ba65b41e9c094b7a2b1497be2dfb97e059ce59938e2525f4786bb1ba07

```md
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
```

## openspec/changes/datamind-core/specs/web-ui/spec.md

- Source: openspec/changes/datamind-core/specs/web-ui/spec.md
- Lines: 1-52
- SHA256: c115d98c48f871a2fd5d0e3b47ea3804d7dcff8102abd26a0963bf1eb0e90687

```md
## ADDED Requirements

### Requirement: Three-Panel Layout
The system SHALL provide a web interface with three panels: a left sidebar for data and script browsing, a central panel for AI dialogue, and a right panel for context visualization.

#### Scenario: Default layout
- **WHEN** user opens the web UI
- **THEN** all three panels are visible: sidebar (data/files), center (chat), right (lineage + context)

### Requirement: Data Sidebar
The left sidebar SHALL display datasets organized by raw/ and processed/ folders. Each dataset entry SHALL show name, row count, column count, and a link to its generating script (for processed datasets). The sidebar SHALL support drag-and-drop file upload for adding new raw datasets.

#### Scenario: Drag and drop CSV upload
- **WHEN** user drags a CSV file from their desktop onto the sidebar
- **THEN** the file is copied to `data/raw/`, a Dataset node is created in graph.db, and a describe file is auto-generated

#### Scenario: Click processed dataset for lineage
- **WHEN** user clicks a processed dataset in the sidebar
- **THEN** the right panel highlights the dataset's position in the lineage graph and shows its generating script

### Requirement: Chat Panel
The central panel SHALL provide a dialogue interface where users can type messages to the AI, invoke skills with `/skill` commands, and see AI responses including proposed code, analysis results, and gate approval prompts. Generated code SHALL be displayed inline with syntax highlighting.

#### Scenario: Chat interaction
- **WHEN** user types a message in the chat input
- **THEN** the message appears in the conversation and the AI responds based on project context

#### Scenario: Skill invocation display
- **WHEN** user invokes `/skill data-cleaning sales.csv`
- **THEN** the chat shows the skill workflow steps as they execute, with gate prompts rendered as interactive approval buttons

#### Scenario: Code display
- **WHEN** AI generates a processing script
- **THEN** the code is displayed inline with syntax highlighting and a "View in Scripts" link

### Requirement: Context Panel
The right panel SHALL display the live lineage graph, recent decisions from decisions.jsonl, and active parameters from params.json. The lineage graph SHALL update in real-time as new datasets and scripts are created.

#### Scenario: Lineage graph updates
- **WHEN** a new script is generated and executed
- **THEN** the lineage graph in the right panel adds the new node and edge immediately

#### Scenario: Decision log display
- **WHEN** a new decision is recorded in decisions.jsonl
- **THEN** the recent decisions list in the right panel shows the new entry

### Requirement: Session Context Indicator
The web UI SHALL display the current context status: whether context has been loaded, the last session timestamp, the current checkpoint version, and a summary of what was injected.

#### Scenario: Context status display
- **WHEN** a new session starts
- **THEN** the UI shows "Context: Ready ✓" with details of what was injected (datasets, decisions, checkpoint version)
```

