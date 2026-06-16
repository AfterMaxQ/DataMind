---
skill: report-generation
version: 2
---
# Report Generation

**Purpose:** Generate a structured data science report from findings, models, and results.

**Inputs:** All prior outputs: exploration findings, feature importance, model metrics.

## Workflow

1. **Load Findings** (AUTO) - Collect all discoveries, model metrics, and exploration results from L1+L2
2. **Build Sections** (AUTO) - Generate report outline: executive summary, methodology, results, conclusions
3. **Gate: Review Outline** (GATE) - Present draft report outline for human review
4. **Generate Report** (AUTO) - Expand outline into full report with charts and tables
5. **Gate: Final Approval** (GATE) - Present final report for human sign-off
6. **Archive** (AUTO) - Archive report and sources for traceability

## Outputs

- Final report document