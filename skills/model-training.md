# Model Training

**Purpose:** Train and tune machine learning models on feature-engineered data.

**Inputs:** A feature-engineered dataset path from data/processed/.

## Workflow

1. **Prepare Data** (AUTO) — Load features, split train/test, establish baseline metrics
2. **Select Models** (AUTO) — Identify candidate models suitable for the problem type
3. **Gate: Model Choice** (GATE) — Present candidate models and rationale for human selection
4. **Train** (AUTO) — Train selected models with cross-validation
5. **Evaluate** (AUTO) — Run final evaluation on test set, generate performance report
6. **Gate: Results** (GATE) — Present evaluation results for human sign-off
7. **Archive** (AUTO) — Archive model artifacts and reports for traceability

## Outputs

- Trained model artifacts
- Evaluation report in describe/
- Model training script in scripts/
- Execution log in executions/
- Model metrics logged to discoveries.jsonl
