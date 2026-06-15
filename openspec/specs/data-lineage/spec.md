# data-lineage Specification

## Purpose
TBD - created by archiving change datamind-core. Update Purpose after archive.
## Requirements
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
The system SHALL enable reproducing any processed dataset by tracing its lineage back to raw data ancestors and re-running the script chain in dependency order.

#### Scenario: Reproduce processed dataset
- **WHEN** user requests to reproduce `data/processed/sales_agg.parquet`
- **THEN** the system traces lineage back to `data/raw/sales.csv` and re-runs `clean_nulls.py` then `aggregate.py` in order

#### Scenario: Reproduce with multi-parent dataset
- **WHEN** user requests to reproduce a dataset created by merging two parents
- **THEN** the system traces both parent lineages back to raw data and re-runs all scripts in topological order

### Requirement: Materialized View Rebuild
The system SHALL provide a mechanism to rebuild the current dataset state by reading execution logs from `executions/` in chronological order and replaying each recorded operation against the graph database. This SHALL complete the event sourcing read path.

#### Scenario: Rebuild from execution logs
- **WHEN** the materialized view is stale or corrupted
- **THEN** reading `executions/` in timestamp order and replaying each operation reconstructs the full dataset state in graph.db

#### Scenario: Rebuild with monotonic timestamps
- **WHEN** replaying execution logs to rebuild state
- **THEN** events are applied in monotonic counter order, ensuring deterministic reconstruction

