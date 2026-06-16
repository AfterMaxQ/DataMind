# DataMind Studio

AI-native data science research system — captures what you did, why you did it, and what you learned, then packs that knowledge for AI consumption across sessions.

## Architecture

DataMind tracks your research across four layers:

| Layer | Service | Purpose |
|-------|---------|---------|
| L1 | **Data Lineage** | Track *what* happened to data — scripts as graph edges, auto-describe on every file |
| L2 | **Cognitive Journey** | Capture *why* — decisions, explorations, discoveries, parameter sweeps |
| L3 | **Context Assembly** | Priority-ordered context packing for AI injection with token budgeting |
| L4 | **Skill System** | Encoded workflows (SKILL.md) with AUTO/GATE steps, powered by LangGraph |

## Installation

```bash
git clone <repo-url>
cd DataMind-Studio
pip install -e ".[dev]"
```

### LLM Configuration

Edit `.datamind/config.yaml` after `datamind init`:

```yaml
llm:
  provider: openai        # openai | deepseek | ollama
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}
  api_base: https://api.openai.com/v1
```

## Quick Start

```bash
# Initialize a DataMind project
datamind init --name my-project /path/to/project

# Drop data files into data/raw/, then ingest
datamind context inject /path/to/project

# Query lineage
datamind lineage query /path/to/project --dataset data/raw/sales.csv
```

## Web UI

```bash
# Terminal 1 — Backend (requires datamind init first)
uvicorn serve:app --host 127.0.0.1 --port 9000 --reload

# Terminal 2 — Frontend
cd web-ui && npm install && npm run dev
```

Open `http://localhost:5173`. The API runs at `http://127.0.0.1:9000`.

### Features

- **Chat panel** — streamed LLM responses with skill context
- **Data sidebar** — browse registered datasets
- **Lineage graph** — visualize upstream/downstream data dependencies
- **Context panel** — inspect assembled AI context
- **Gate approval** — interactive approval for GATE phases in skill workflows
- **Model switching** — hot-swap between OpenAI/DeepSeek/Ollama models

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/datasets` | List registered datasets |
| POST | `/datasets/register` | Register a dataset file |
| GET | `/lineage/{id}` | Query ancestors & descendants |
| GET | `/context` | Get assembled context |
| POST | `/decisions` | Log a decision |
| GET | `/decisions` | List recent decisions |
| GET | `/skills` | List available skills |
| GET | `/models` | List available LLM models |
| POST | `/models/switch` | Switch active model |
| GET | `/chat/stream` | SSE streamed chat (query: `message`, `skill`, `target`) |
| GET | `/skill-sessions` | List skill sessions |
| POST | `/skill/gate` | Approve a GATE phase |
| GET | `/usage` | Token usage report |
| WS | `/ws` | WebSocket for real-time updates |
| POST | `/upload` | File upload (auto-register as dataset) |

## CLI Reference

```
datamind init <project_root> [--name]     Initialize a DataMind project
datamind lineage query <project_root>      Query data lineage
datamind context inject <project_root>     Generate context for AI injection
datamind skill list <project_root>         List available skills
```

## Project Structure

```
.datamind/              # Project knowledge store
  config.yaml           # LLM configuration
  graph.db              # SQLite knowledge graph
  checkpoints.db        # LangGraph checkpoint store
  context/              # Auto-generated context files
  decisions.jsonl       # Append-only decision log
  exploration.json      # Exploration tree
  params.json           # Parameter sweep history
  discoveries.jsonl     # Discovery log
data/
  raw/                  # Immutable original data
  processed/            # Derived datasets
scripts/                # AI-generated analysis scripts
describe/               # Auto data.describe() per dataset
executions/             # Execution log artifacts
skills/                 # SKILL.md workflow definitions
web-ui/                 # Vue 3 + Vite frontend
  src/
    components/         # ChatPanel, DataSidebar, LineageGraph, etc.
    composables/        # useChat, useWebSocket
    stores/             # Pinia stores (session, theme)
tests/
  unit/                 # Fast unit tests (no I/O)
  integration/          # Integration tests
  e2e/                  # End-to-end workflow tests
datamind/
  api/                  # FastAPI app, WebSocket, debug endpoints
  cli/                  # Click CLI
  engine/               # Core services (Project, lineage, cognition, skills, LangGraph agent)
  mcp/                  # MCP server
```

## Testing

```bash
pytest tests/unit/ -v         # Unit tests
pytest tests/integration/ -v  # Integration tests
pytest tests/e2e/ -v          # E2E workflow tests
pytest -q                     # All tests
```

## Development

This project follows the [Comet](https://github.com/anthropics/claude-code) development workflow (OpenSpec + Superpowers). See `CLAUDE.md` for session rules.

Key conventions:
- **TDD first** — write a failing test, watch it fail, then write minimal code
- **Surgical changes** — touch only what you must, match existing style
- **Commit per task** — commit immediately after each task passes review
