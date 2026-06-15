## Why

AI agents in data science suffer from **session amnesia**. Every new conversation window resets the AI's understanding of the project — what data exists, how it was processed, why certain decisions were made, which approaches were tried and failed. Data scientists spend significant time re-explaining project context instead of doing actual work. This problem is acute because data science is inherently cumulative: each cleaning step, each exploration, each failed model attempt builds understanding that future work depends on.

Existing tools track artifacts (DVC tracks data versions, MLflow tracks experiments, Jupyter notebooks capture code) but **none capture the full cognitive journey** — the decisions, the dead ends, the parameters, the accidental discoveries — in a structured format that AI agents can consume across sessions.

## What Changes

- **Data lineage engine**: Automatic tracking of raw → processed data transformations. Scripts serve as edges between dataset nodes. Every dataset gets an auto-generated description (schema, statistics, distributions) so AI never needs to re-read raw files.
- **Cognitive journey capture**: Structured logging of decisions (what, why, alternatives, implications), exploration trees (including dead ends), parameter snapshots (normalization bounds, split dates, hyperparameters), and discovery feed (accidental insights, structured chronologically).
- **Context assembly & injection**: Priority-ordered, token-budget-aware context manifest assembled from lineage + cognition layers. Injected at the start of every AI session so the AI immediately understands the project.
- **Skill orchestration system**: Encoded data science workflows (data-cleaning, feature-engineering, model-training, report-generation) with human approval gates. Skills read project context, execute within a defined structure, and write results back to all layers. Humans only appear at decision gates — judgment, not labor.
- **Three-panel web interface**: Data sidebar (raw/processed browsing with lineage links), central dialogue panel (skill invocation, AI interaction, code display), right context panel (live lineage graph, recent decisions, active parameters).

## Capabilities

### New Capabilities

- `context-engine`: Core knowledge graph and event store. Manages the SQLite-based graph database, event sourcing for all AI actions, and the structured project directory format (`.datamind/`).
- `data-lineage`: Data lineage tracking with script-as-edge pattern. Auto-generates data descriptions for every dataset. Tracks raw → processed relationships through processing scripts.
- `cognitive-journey`: Decision log, exploration tree, parameter registry, and discovery feed. Captures the WHY and LEARNED alongside the WHAT.
- `context-assembly`: Priority-ordered context packer that generates context manifest files (PROJECT.md, DATASETS.md, HISTORY.md, CHECKPOINT.md) for AI session injection.
- `skill-system`: Skill definitions with structured workflows (analyze → propose → gate → execute → validate → gate). Built-in skills for common data science tasks. Custom skill creation support. Skill pipeline composition.
- `web-ui`: Three-panel web application (sidebar, chat, context panel) for interacting with the system. Drag-drop dataset upload, skill invocation, code display, and live lineage visualization.

### Modified Capabilities

<!-- No existing capabilities to modify — this is a greenfield project. -->

## Impact

- **New project**: Greenfield development. No existing code to modify.
- **Tech stack (proposed)**: Python backend (FastAPI or similar), SQLite for graph storage, Vue for web UI, MCP integration for Claude Code interoperability.
- **Dependencies**: None on existing systems. Will define `.datamind/` as a portable project format.
- **Deployment**: Local-first (runs alongside the user's tools). Web UI served locally.
