# cognitive-journey Specification

## Purpose
TBD - created by archiving change datamind-core. Update Purpose after archive.
## Requirements
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

