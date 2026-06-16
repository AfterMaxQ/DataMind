---
skill: data-exploration
version: 2
---
# Data Exploration

**Purpose:** Explore a dataset to understand distributions, correlations, patterns, and generate visualizations.

**Inputs:** A dataset path (raw or processed) and optional exploration parameters.

## Workflow

1. **Read Describe** (AUTO) - Load describe/ statistics for the dataset
2. **Explore Patterns** (AUTO) - Compute correlations, distributions, outliers, generate exploratory charts
3. **Generate Viz** (AUTO) - Create standard EDA visualizations (histograms, box plots, scatter matrix)
4. **Gate: Review Findings** (GATE) - Present findings and charts to human for review and direction
5. **Archive** (AUTO) - Archive exploration results and charts for traceability

## Outputs

- Exploration charts saved to describe/
- Findings logged to discoveries.jsonl
- Exploration tree updated in exploration.json