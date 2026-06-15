# data-lineage Delta Specification

## Purpose
Add reproducibility execution and materialized view rebuild to the data lineage capability.

## ADDED Requirements

### Requirement: Materialized View Rebuild
The system SHALL provide a mechanism to rebuild the current dataset state by reading execution logs from `executions/` in chronological order and replaying each recorded operation against the graph database. This SHALL complete the event sourcing read path.

#### Scenario: Rebuild from execution logs
- **WHEN** the materialized view is stale or corrupted
- **THEN** reading `executions/` in timestamp order and replaying each operation reconstructs the full dataset state in graph.db

#### Scenario: Rebuild with monotonic timestamps
- **WHEN** replaying execution logs to rebuild state
- **THEN** events are applied in monotonic counter order, ensuring deterministic reconstruction

### Requirement: Reproducibility
The system SHALL enable reproducing any processed dataset by tracing its lineage back to raw data ancestors and re-running the script chain in dependency order.

#### Scenario: Reproduce processed dataset
- **WHEN** user requests to reproduce `data/processed/sales_agg.parquet`
- **THEN** the system traces lineage back to `data/raw/sales.csv` and re-runs `clean_nulls.py` then `aggregate.py` in order

#### Scenario: Reproduce with multi-parent dataset
- **WHEN** user requests to reproduce a dataset created by merging two parents
- **THEN** the system traces both parent lineages back to raw data and re-runs all scripts in topological order
