# Data Cleaning

**Purpose:** Clean raw data files by detecting and fixing common issues: missing values, outliers, type mismatches, duplicates.

**Inputs:** A dataset path from data/raw/ (CSV, Parquet, Excel).

## Workflow

1. **Analyze** (AUTO) — Read the describe/ output for the dataset, sample first 100 rows, and identify data quality issues
2. **Propose Strategy** (AUTO) — Generate a cleaning strategy: which columns need what treatment, with rationale
3. **Gate: Approve** (GATE) — Present the proposed strategy to the human for approval, rejection, or modification
4. **Execute** (AUTO) — Generate and run a cleaning script (scripts/clean_*.py) that applies the approved strategy
5. **Validate** (AUTO) — Compare before/after statistics, verify no data loss, check output integrity
6. **Gate: Result** (GATE) — Show validation results to the human for final sign-off
7. **Archive** (AUTO) — Archive session artifacts, scripts, and reports for traceability

## Outputs

- Cleaned dataset in data/processed/
- Cleaning script in scripts/
- Describe file in describe/ for the cleaned dataset
- Execution log in executions/
- Graph edges linking raw — script — cleaned
