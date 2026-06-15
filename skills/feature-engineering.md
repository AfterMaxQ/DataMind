# Feature Engineering

**Purpose:** Create and select features from a cleaned dataset for model training.

**Inputs:** A cleaned dataset path from data/processed/.

## Workflow

1. **Analyze Target** (AUTO) — Identify target variable and understand its distribution
2. **Propose Features** (AUTO) — Generate candidate features (transformations, encoding, interactions)
3. **Gate: Approve Set** (GATE) — Present candidate feature set for human approval
4. **Generate Code** (AUTO) — Generate feature engineering script (scripts/features_*.py) and run it
5. **Validate** (AUTO) — Check feature distributions, correlations with target, missing values

## Outputs

- Feature-engineered dataset in data/processed/
- Feature engineering script in scripts/
- Feature importance report in describe/
- Execution log in executions/
