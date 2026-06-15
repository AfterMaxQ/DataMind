# context-assembly Delta Specification

## Purpose
Add automatic context file refresh triggered by project state changes.

## MODIFIED Requirements

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
