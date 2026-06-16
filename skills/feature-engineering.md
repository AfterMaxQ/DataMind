---
skill: feature-engineering
version: 2
routing:
  gate-4: { reject: propose-features }
tools:
  phase-1: [read_csv, read_parquet, describe_dataset]
---
# Feature Engineering

**Purpose:** Create and select features from a cleaned dataset for model training.

**Inputs:** A cleaned dataset path from data/processed/.

## Workflow

1. **Load Data** (AUTO) — Load cleaned dataset and verify schema
2. **Analyze Features** (AUTO) — Identify target variable and understand its distribution
3. **Propose Features** (AUTO) — Generate candidate features (transformations, encoding, interactions) with rationale
4. **Gate: Approve** (GATE) — Present candidate feature set for human approval
5. **Engineer Features** (AUTO) — Generate feature engineering script (scripts/features_*.py) and run it
6. **Validate** (AUTO) — Check feature distributions, correlations with target, missing values
7. **Gate: Result** (GATE) — Show validation results to human for sign-off
8. **Archive** (AUTO) — Archive feature set and scripts for traceability

## Outputs

- Feature-engineered dataset in data/processed/
- Feature engineering script in scripts/
- Feature importance report in describe/
- Execution log in executions/
