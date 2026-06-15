## Context

DataMind Studio is a greenfield project. No existing code or architecture to integrate with. The system addresses AI session amnesia in data science workflows — the problem that every new AI conversation starts with zero knowledge of the project's data, history, decisions, and discoveries.

The target users are data scientists and analysts who use AI tools (Claude Code, ChatGPT, etc.) alongside their data work. They need a system that:
- Automatically captures project context without manual effort
- Injects relevant context into new AI sessions
- Supports both AI-driven and manual data workflows
- Works locally (no cloud dependency required)

## Goals / Non-Goals

**Goals:**
- Define a portable project format (`.datamind/`) that captures data lineage and cognitive journey
- Provide automatic context injection for AI sessions
- Enable skill-based workflow orchestration with human approval gates
- Deliver a three-panel web UI for browsing data, chatting with AI, and viewing context

**Non-Goals:**
- Cloud-hosted collaboration (v1 is single-user, local-first)
- Real-time multiplayer editing
- Replacement for Jupyter/VSCode (DataMind complements existing tools)
- Data storage/warehousing (DataMind references data, doesn't host it)
- Model serving or deployment

## Decisions

### Decision 1: Four-Layer Architecture

**Chosen**: L1 Lineage → L2 Cognition → L3 Assembly → L4 Skills

Layer 1 tracks WHAT happened to data (graph, scripts, descriptions). Layer 2 tracks WHY and what was learned (decisions, explorations, params, discoveries). Layer 3 assembles curated context from both layers for AI injection. Layer 4 orchestrates skills that read from and write to all lower layers.

**Alternatives considered**:
- **Monolithic context store**: Simpler but conflates data tracking with decision tracking. Harder to evolve independently.
- **Plugin architecture**: Too flexible for v1. Adds complexity without clear benefit.

**Rationale**: The separation between "what happened to data" and "why it happened" emerged from walking through a real financial analyst workflow. Data lineage tools exist (DVC) and experiment trackers exist (MLflow), but none connect them. The four layers are not arbitrary — each one solves a distinct problem discovered in the analyst journey.

### Decision 2: SQLite for Knowledge Graph Storage

**Chosen**: SQLite with a relational schema representing typed nodes and edges. Not a dedicated graph database (Neo4j, ArangoDB), not a vector database.

**Rationale**:
- SQLite is embedded, zero-config, works offline — matches local-first deployment
- Data lineage is inherently relational (datasets, scripts, executions, parameters all have structured schemas)
- Graph queries (find ancestors, descendants) can be expressed as recursive CTEs in SQL
- Vector search is not needed for this use case (decisions and discoveries are tagged and structured, not semantically searched)
- Single file (graph.db) is portable alongside the project

### Decision 3: Script-as-Edge Pattern

**Chosen**: The processing script filename/ID serves as the edge between dataset nodes in the lineage graph. No separate mapping table.

Example: `scripts/clean_nulls.py` is the edge from `raw/sales.csv` to `processed/sales_clean.csv`.

**Alternatives considered**:
- **Separate edge table in graph.db**: More flexible but redundant — the script already uniquely identifies the transformation.
- **Content-hash based edges**: Content-addressable but fragile when scripts are modified.

**Rationale**: The script is the transformation. Making it the edge means reading the lineage graph immediately tells you which script to re-run to reproduce any dataset. This is the simplest solution that solves the problem.

### Decision 4: Event Sourcing as the Write Model

**Chosen**: Every AI action is written as an immutable event log entry first. The knowledge graph (graph.db), decisions.jsonl, params.json, etc. are materialized views rebuilt from the event log.

**Rationale**:
- Audit trail: every AI action is traceable
- Replay: can reconstruct project state from any point
- Resilience: if a materialized view gets corrupted, rebuild from events
- The execution log files (`executions/*.md`) are the event source, not a separate database

### Decision 5: Context Packing Algorithm (Priority-Ordered, Not Semantic Search)

**Chosen**: Context is assembled using priority tiers, not vector similarity search.

Priority tiers:
1. ALWAYS: PROJECT.md + all DATASETS.md
2. RECENT: last N decisions, executions, discoveries
3. RELEVANT: graph traversal for query-related nodes (tag-based, not embedding-based)
4. COMPRESSED: CHECKPOINT.md (periodically regenerated dense summary)

**Alternatives considered**:
- **RAG/vector search**: Overkill. Data lineage and decisions are structured, not semantically fuzzy. Embedding-based retrieval would surface loosely related content instead of the exact decisions and parameters needed.
- **LLM summarization of full history**: Too expensive. Better to use checkpoint compression periodically (every N sessions or when significant changes accumulate).

### Decision 6: Skill System Modeled After OpenSpec + Superpowers

**Chosen**: Skills are standalone markdown definitions (SKILL.md) with structured workflow steps. Each step is either AUTO (AI executes) or GATE (human approves/rejects). Skills compose into pipelines.

**Rationale**:
- OpenSpec and Superpowers already validated this pattern: skills encode workflows, AI executes within constraints, humans judge at decision points
- Markdown-based definitions are AI-readable and human-editable
- Custom skills can be created by users or AI for domain-specific workflows

### Decision 7: Python Backend + Web UI

**Chosen**: Python backend (FastAPI) serving a Vue-based three-panel web UI. Runs locally.

**Alternatives considered**:
- **Electron app**: Heavier, more complex distribution. Web UI with local server is simpler.
- **CLI-only**: The user explicitly wants a visual interface with drag-drop, sidebar, and chat panels.
- **VSCode extension**: Limits audience. Web UI is more universal.

## Risks / Trade-offs

- **[Risk] SQLite graph queries become slow with large lineage graphs** → Mitigation: Start with SQLite. If performance degrades (10k+ nodes), add a graph traversal layer or migrate to DuckDB for analytical queries while keeping SQLite for metadata.
- **[Risk] Event log files grow unbounded** → Mitigation: Checkpoint compression aggregates old execution logs into dense summaries. Archive logs older than configurable threshold.
- **[Risk] Skill definitions become stale as data science practices evolve** → Mitigation: Skills are versioned and user-customizable. Built-in skills are a starting point, not a constraint.
- **[Risk] Multi-user collaboration conflicts in .datamind/** → Mitigation: v1 is explicitly single-user. If multi-user is needed later, git-based merging or a server mode can be added.
- **[Trade-off] Local-first means no cloud sync in v1** → Chosen explicitly. The `.datamind/` directory is portable and can be synced via git, Dropbox, etc. Cloud sync can be added later without changing the architecture.
