---
comet_change: datamind-core
role: technical-design
canonical_spec: openspec
---

# DataMind Core — Technical Design

## Architecture Overview

Four-layer system that captures project knowledge for AI consumption across sessions.

```
┌──────────────────────────────────────────────────────────┐
│  L4: Skill Orchestration  (skills/)                       │
│  Encoded workflows with AUTO/GATE steps. Human judgment   │
│  at decision points.                                      │
├──────────────────────────────────────────────────────────┤
│  L3: Context Assembly     (context/)                      │
│  Priority-ordered, token-budget-aware manifest generation │
│  from L1 + L2.                                            │
├──────────────────────────────────────────────────────────┤
│  L2: Cognitive Journey    (decisions, exploration, params,│
│                             discoveries)                  │
│  WHY and what was learned. Rationale, dead ends, params,  │
│  accidental insights.                                     │
├──────────────────────────────────────────────────────────┤
│  L1: Data Lineage         (graph.db, describe/, scripts/) │
│  WHAT happened to data. Graph nodes + script-as-edge.     │
│  Auto data.describe for every dataset.                    │
└──────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: Python 3.11+, FastAPI (REST layer, loaded on-demand for Web UI)
- **Storage**: SQLite (graph.db) with WAL mode, JSONL files for append-only logs
- **Frontend**: Vue 3 (Composition API), three-panel layout
- **AI Integration**: MCP Server wrapping the engine, CLI/SDK for universal access
- **Deployment**: Local-first, single-user v1

## Component Architecture

Domain services + Project facade. Each service owns its storage format. Dependencies injected via constructor. `Project` composes services, contains no business logic.

```
datamind/
├── engine/
│   ├── lineage.py      → LineageService(graph_db, describe_dir, scripts_dir)
│   ├── cognition.py    → CognitionService(decisions_file, exploration_file,
│                           params_file, discoveries_file)
│   ├── assembly.py     → AssemblyService(lineage_svc, cognition_svc)
│   ├── skills.py       → SkillService(skills_dir, lineage_svc, cognition_svc,
│                           assembly_svc)
│   └── project.py      → Project (composition, no logic)
├── cli/
│   └── main.py         → Click CLI: datamind init, context inject, lineage query
├── mcp/
│   └── server.py       → MCP tools: read_context, register_dataset, log_decision
├── api/
│   └── app.py          → FastAPI (Vue Web UI backend)
└── web/                 → Vue 3 application (three-panel layout)
```

### Service Responsibilities

| Service | Reads | Writes | Key API |
|---------|-------|--------|---------|
| LineageService | graph.db, data/ | graph.db, describe/ | add_dataset, query_ancestors, query_descendants, auto_describe |
| CognitionService | decisions.jsonl, exploration.json, params.json, discoveries.jsonl | same files (append) | log_decision, add_exploration_node, register_params, add_discovery |
| AssemblyService | lineage_svc, cognition_svc | context/*.md | assemble_manifest, generate_checkpoint, refresh_context |
| SkillService | skills_dir, assembly_svc, lineage_svc, cognition_svc | delegates to lower services | load_skill, execute_step, handle_gate, compose_pipeline |

## Data Model

### SQLite Schema (graph.db)

```sql
-- Nodes
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,           -- 'dataset' | 'script' | 'execution' | 'finding' | 'checkpoint'
    name TEXT NOT NULL,
    path TEXT,                    -- filesystem path for datasets/scripts
    metadata JSON,                -- type-specific fields
    created_at TEXT NOT NULL
);

-- Edges
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES nodes(id),
    target_id TEXT NOT NULL REFERENCES nodes(id),
    edge_type TEXT NOT NULL,      -- 'GENERATED_BY' | 'PRODUCED' | 'USED_INPUT' | 'TRIGGERED' | 'DISCOVERED_DURING'
    metadata JSON,
    created_at TEXT NOT NULL
);

-- Indexes for traversal
CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
```

### JSONL Append-Only Logs

```
decisions.jsonl:    {"id":"d14","what":"forward fill","why":"stocks don't interpolate on weekends","alternatives":["interpolation","drop"],"implications":"preserves weekend gap structure","timestamp":"2026-06-15T10:15:00Z"}
discoveries.jsonl:  {"id":"f3","tag":"model-weakness","finding":"Accuracy drops 15% during earnings season","linked_code":"scripts/backtest.py","linked_data":"processed/features.parquet","timestamp":"2026-06-15T16:30:00Z"}
```

### JSON State Files

```
exploration.json:   tree of {id, status: SELECTED|REJECTED|EXPLORATORY, reason?, parent_id, children[]}
params.json:        {script_id: {run_id: {key: value, ...}}}
```

## Context Packing Algorithm

Priority-ordered, not semantic search.

```
Priority 1 (ALWAYS):    PROJECT.md + all DATASETS.md           ~2.5k tokens
Priority 2 (RECENT):    last 5 decisions + executions + discoveries  ~8k tokens
Priority 3 (RELEVANT):  graph traversal for query-tagged nodes      ~3k tokens
Priority 4 (COMPRESSED): CHECKPOINT.md (periodically regenerated)    ~2k tokens

Target budget: ~40k tokens. Truncate from bottom up when exceeded.
```

CHECKPOINT.md regenerated when ≥10 new execution logs accumulate since last checkpoint.

## Skill System

Skills defined as SKILL.md files, modeled after OpenSpec + Superpowers pattern.

### Workflow Step Types

- **AUTO**: AI executes autonomously, writes results
- **GATE**: AI presents proposal, human approves/rejects/modifies

### Built-in Skills

| Skill | Steps |
|-------|-------|
| data-cleaning | Analyze(AUTO) → Propose Strategy(AUTO) → **Gate: Approve** → Execute(AUTO) → Validate(AUTO) → **Gate: Result** |
| data-exploration | Read Describe(AUTO) → Explore Patterns(AUTO) → Generate Visualizations(AUTO) → **Gate: Review Findings** |
| feature-engineering | Analyze Target(AUTO) → Propose Features(AUTO) → **Gate: Approve Set** → Generate Code(AUTO) → Validate(AUTO) |
| model-training | Load Features(AUTO) → Baseline(AUTO) → Tune(AUTO) → **Gate: Select Model** → Evaluate(AUTO) |
| report-generation | Gather Findings(AUTO) → Structure Report(AUTO) → **Gate: Review Draft** → Export(AUTO) |

### Pipeline Composition

Skills chain: `data-cleaning → feature-engineering → model-training → report-generation`

Each skill reads context manifest, writes to all lower layers. Human only at GATE steps.

## Error Handling

**Error as artifact**: Failed executions are first-class logs alongside successes. The error IS the context for the next AI session.

**Error types**:
- `ScriptExecutionError`: stderr, exit_code, linked script path
- `DataIntegrityError`: affected graph node IDs
- `GateRejectionError`: normal control flow (not a bug)
- `ContextAssemblyError`: list of missing sources, degraded manifest generated

**Per-layer boundaries**:
- `AssemblyService` failure → does NOT block skill execution (assembly is read-only)
- Skill AUTO step failure → recorded, retry/fallback offered, never silently skipped
- GATE rejection → return to proposal step, do not advance
- `CognitionService` corruption → skip corrupted entry, preserve rest
- Lineage script failure → graph.db NOT rolled back; execution log records stderr + data snapshot

**Write safety**:
- SQLite: WAL mode + transactions, never enters inconsistent state
- JSONL: append-only, corrupted entries skipped and flagged, rest preserved
- Script execution: failure does NOT roll back the "attempt" fact

## Testing Strategy

Three-layer combination:

```
Layer 3: E2E Snapshot Tests (3-5 full scenarios)
  ├─ Financial sentiment analysis: raw → clean → features → model → report
  ├─ Multi-branch exploration: one raw → multiple processed variants
  └─ Error recovery: script failure + retry with corrected params

  Compare entire .datamind/ output against golden/ snapshots.
  '--update-snapshots' flag to accept new expected output.

Layer 2: Service Integration Tests (real files, no mocks)
  ├─ LineageService: write datasets → query ancestors/descendants
  ├─ CognitionService: append decisions → read last N
  ├─ AssemblyService: given lineage + cognition → verify manifest structure
  └─ SkillService: load SKILL.md → execute AUTO steps → verify GATE pause

Layer 1: Pure Function Unit Tests (no I/O)
  ├─ Context packing priority algorithm
  ├─ Token budget truncation logic
  ├─ Parameter extraction regex
  └─ Skill parser
```

**Core principle**: Storage-related tests use real files (no mocks). Pure algorithms use unit tests. Snapshot tests verify what the AI sees.

## Project Format (.datamind/)

```
.datamind/
├── graph.db              ← SQLite knowledge graph
├── context/              ← auto-generated context files
│   ├── PROJECT.md        ← project overview
│   ├── DATASETS.md       ← all dataset schemas
│   ├── HISTORY.md        ← recent activity
│   ├── EXPLORATION.md    ← active exploration branch
│   ├── PARAMS.md         ← active parameters
│   ├── CHECKPOINT.md     ← compressed understanding
│   └── CONTEXT_MANIFEST.md ← priority-ordered injection
└── config.yaml           ← project configuration

data/
├── raw/          ← immutable originals
└── processed/    ← derived datasets

scripts/          ← AI-generated, script-as-edge
describe/         ← auto data.describe per dataset
executions/       ← immutable event logs
skills/           ← built-in + custom SKILL.md files
```

## Sequence: Full Workflow

```
User drops sales.csv in sidebar
  → LineageService registers Dataset node, auto-describes

User: "/skill data-cleaning sales.csv"
  → SkillService loads skill, reads assembly context
  → AUTO: Analyze (reads describe/, samples data)
  → AUTO: Propose strategy (finds nulls, proposes fixes)
  → GATE: Human sees proposal, clicks APPROVE (with forward fill tweak)
  → AUTO: Execute (generates scripts/clean_sales.py, runs it)
  → AUTO: Validate (checks output stats)
  → GATE: Human sees before/after, clicks APPROVE
  → All writes: graph.db updated, decisions.jsonl appended,
    execution log saved, describe/clean_sales.csv.describe.md generated

Next AI session:
  → AssemblyService reads all layers, assembles CONTEXT_MANIFEST.md
  → AI reads manifest, knows: datasets, lineage, decisions, params,
    last execution, checkpoint state
  → Ready to continue without re-explanation
```
