# context-assembly Specification

## Purpose
TBD - created by archiving change datamind-core. Update Purpose after archive.
## Requirements
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

