# Model Training

**Purpose:** Train and tune machine learning models on feature-engineered data.

**Inputs:** A feature-engineered dataset path from data/processed/.

## Workflow

1. **Load Features** (AUTO) — Load features, split train/test, establish baseline metrics
2. **Baseline** (AUTO) — Train a simple baseline model and record performance
3. **Tune** (AUTO) — Perform hyperparameter tuning with cross-validation
4. **Gate: Select Model** (GATE) — Present candidate models and metrics for human selection
5. **Evaluate** (AUTO) — Run final evaluation on test set, generate report

## Outputs

- Trained model artifacts
- Evaluation report in describe/
- Model training script in scripts/
- Execution log in executions/
- Model metrics logged to discoveries.jsonl
