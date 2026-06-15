# DataMind Studio

AI-native data science research system. Captures project knowledge across four layers for AI consumption across sessions.

## Quick Start

```bash
pip install -e ".[dev]"
datamind init --name my-project /path/to/project
```

Drop data files into `data/raw/`, then:

```bash
datamind context inject /path/to/project
```

## Architecture

| Layer | Name | What It Tracks |
|-------|------|---------------|
| L1 | Data Lineage | WHAT happened to data (graph.db, script-as-edge, auto-describe) |
| L2 | Cognitive Journey | WHY and what was learned (decisions, explorations, discoveries) |
| L3 | Context Assembly | Priority-ordered context packing for AI injection |
| L4 | Skill System | Encoded workflows (SKILL.md) with AUTO/GATE steps |

## CLI Commands

- `datamind init <project_root>` -- Initialize a new DataMind project
- `datamind lineage query <project_root> --dataset <path>` -- Query data lineage
- `datamind context inject <project_root>` -- Generate context for AI
- `datamind skill list <project_root>` -- List available skills

## Testing

```bash
pytest tests/unit/ -v        # Unit tests (no I/O)
pytest tests/integration/ -v  # Integration tests (real files)
pytest tests/e2e/ -v          # End-to-end workflow tests
```

## Project Structure

```
.datamind/          # Project knowledge store
  graph.db          # SQLite knowledge graph
  context/          # Auto-generated context files
  decisions.jsonl   # Append-only decision log
  exploration.json  # Exploration tree
data/
  raw/              # Immutable original data
  processed/        # Derived datasets
scripts/            # AI-generated scripts
describe/           # Auto data.describe per dataset
skills/             # SKILL.md workflow definitions
```
