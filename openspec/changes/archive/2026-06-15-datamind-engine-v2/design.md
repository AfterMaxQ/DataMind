## Context

v1 established the four-layer engine: L1 Data Lineage (graph.db, describe, scripts), L2 Cognitive Journey (decisions, exploration, params, discoveries), L3 Context Assembly (priority-ordered context packing), L4 Skill System (SKILL.md parsing, AUTO/GATE step tracking). v1's skill system is parse-only — it reads SKILL.md files and tracks step state, but has no execution engine. There is no LLM integration, no agent loop, and skills cannot be interrupted and resumed efficiently.

v2 adds the execution brain: LLM clients, an agent loop, and a Comet-style skill state machine that enables fast interrupt/resume with minimal context re-reading.

The design must remain framework-agnostic at the LLM client layer, reserving a LangGraph migration path for v3 when complex branching/parallel skill pipelines emerge.

## Goals / Non-Goals

**Goals:**
- LLM client abstraction supporting OpenAI-compatible APIs and Ollama local models
- Multi-model switching at runtime with auto-discovery of Ollama models
- System prompt templates as directory of markdown files with variable injection
- Per-session token usage and cost tracking
- Agent loop: context assembly → prompt → LLM call → tool execution → decision recording
- Skill state machine with `.skill.yaml` lifecycle, phase tracking, artifact management
- Interrupt/resume: AI reads `.skill.yaml` and recovers to exact phase without re-execution
- 7 skills rewritten with phase-based definitions (5 existing + 2 new)
- Materialized view rebuild from execution logs, reproducibility, and context auto-refresh
- Chat SSE streaming endpoint

**Non-Goals:**
- Vue 3 Web UI (separate `datamind-web-ui` change)
- LangGraph integration (v3, architecture reserved)
- RAG / vector retrieval / embeddings
- Multi-agent collaboration
- Real-time WebSocket updates beyond SSE

## Decisions

### D1: LLM Client — Custom abstraction over framework

**Decision**: Build a thin `BaseLLMClient` abstract class with `OpenAIClient` and `OllamaClient` implementations. Do NOT use LangChain's LLM abstraction.

**Rationale**: LangChain's LLM wrapper adds ~15 dependencies and abstraction overhead without adding value. The OpenAI Python SDK already provides a clean interface. Ollama exposes an OpenAI-compatible endpoint. The abstraction is ~50 lines, not a framework.

**Alternatives considered**:
- LangChain LLM: Heavy dependency, frequent breaking changes, little benefit over direct SDK calls
- LiteLLM: Good multi-provider proxy but adds a proxy layer; overkill for v2's two providers

### D2: Agent Loop — Custom lightweight, LangGraph-reserved

**Decision**: Implement a custom agent loop in `engine/agent.py` (~120 lines). The LLM client layer (`engine/llm.py`) is designed to be framework-agnostic. When v3 requires LangGraph for complex branching/parallel execution, only `engine/agent.py` needs replacement.

**Rationale**: v2's skill execution is linear (AUTO → GATE → AUTO → GATE). A custom while-loop with interrupt/resume is simpler and more transparent than LangGraph for linear flows. The architecture boundary at `engine/llm.py` ensures framework independence.

**LangGraph migration trigger (v3)**: When skills need parallel execution (multi-model training), conditional branching (REJECT → back to propose), or map-reduce patterns (fan-out validation).

### D3: Skill State Machine — `.skill.yaml` as source of truth

**Decision**: Each skill invocation creates a timestamped session directory under `.datamind/skill-sessions/` containing a `.skill.yaml` state file and phase artifact files. The state file is the single source of truth for phase tracking and recovery.

**Rationale**: Modeled after Comet's `.comet.yaml`. AI reads one file (~200 bytes) and knows: skill name, target, current phase, all phase statuses, artifact paths, and result. No need to re-read SKILL.md, trace execution logs, or parse artifacts. This is the "fast resume" primitive.

```
.datamind/skill-sessions/2026-06-15-sales-cleaning/
├── .skill.yaml          # phase: execute, status: in_progress
├── phase-1-analyze.md   # Analysis output
├── phase-2-strategy.md  # Proposed strategy
├── phase-3-gate.json    # Gate approval record
└── phase-4-execution.json
```

### D4: Prompt Templates — Directory of markdown files

**Decision**: System prompt templates live in a directory as `.md` files with YAML frontmatter for metadata. Templates support `{{ variable }}` injection for context, skills list, datasets, and parameters.

**Rationale**: Markdown is AI-native (both human and LLM readable). Directory structure allows adding/removing templates without code changes. YAML frontmatter provides machine-readable metadata without parsing complexity.

```
prompts/
├── data-scientist.md    # Default: full data science context
├── code-reviewer.md     # Review generated scripts
├── requirement-analyst.md  # requirement-discussion skill
└── archivist.md         # auto-archive skill
```

### D5: Usage Tracking — Per-session aggregation

**Decision**: Track token usage and cost per skill session. Store in `.skill.yaml` under `usage:` field and expose via API. Cost rates configurable per model in `config.yaml`.

**Rationale**: Per-session granularity aligns with the skill session lifecycle. Cost tracking is essential for API-based models. Ollama local models track tokens with zero cost.

### D6: Ollama Model Discovery — `ollama list` auto-scan

**Decision**: On startup, if Ollama provider is configured, run `ollama list` to discover available models. Cache the result with a TTL. Fall back to manually configured model names if the command fails.

**Rationale**: Ollama models change as users pull new ones. Auto-discovery eliminates configuration drift. The `ollama list` command is fast (<100ms) and returns JSON.

### D7: Config — Dual source (file + env vars)

**Decision**: LLM configuration lives in `.datamind/config.yaml`. API keys and sensitive values support `${ENV_VAR}` syntax for environment variable injection. Both sources are merged at load time with env vars taking precedence.

**Rationale**: Config file for discoverability and documentation. Env vars for secrets (12-factor app). The `${}` syntax is widely understood and easy to parse.

## Architecture

```
                         ┌──────────────────────────┐
                         │  User Interface           │
                         │  CLI / API (SSE) / MCP   │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │    Agent Loop             │
                         │    engine/agent.py        │
                         │                           │
                         │  while not done:          │
                         │    context = assemble()   │
                         │    prompt = render()      │
                         │    response = llm.chat()  │
                         │    execute_tools()        │
                         │    record_decisions()     │
                         └──┬───┬───┬───┬──────────┘
                            │   │   │   │
              ┌─────────────┘   │   │   └─────────────┐
              ▼                 │   │                  ▼
    ┌─────────────────┐        │   │        ┌─────────────────┐
    │ engine/llm.py   │        │   │        │ engine/         │
    │ BaseLLMClient   │        │   │        │ skill_state.py  │
    │ OpenAIClient    │        │   │        │ .skill.yaml     │
    │ OllamaClient    │        │   │        │ phase tracking  │
    └─────────────────┘        │   │        └─────────────────┘
              │                │   │
    ┌─────────┴─────────┐     │   │
    │ engine/prompt.py  │     │   │
    │ TemplateManager   │◄────┘   │
    └───────────────────┘         │
    ┌───────────────────┐         │
    │ engine/usage.py   │◄────────┘
    │ UsageTracker      │
    └───────────────────┘
```

## Risks / Trade-offs

- **[Risk] Ollama not installed** → Graceful degradation: skip auto-discovery, use manually configured models
- **[Risk] Custom agent loop insufficient for v3** → Architecture reserves `engine/agent.py` as replacement boundary; `engine/llm.py` is framework-agnostic
- **[Risk] `.skill.yaml` schema evolution** → Version field in schema; migration function for older sessions
- **[Trade-off] Custom LLM abstraction vs LiteLLM** → Fewer providers supported (2 vs 100+), but zero dependency overhead and full control. LiteLLM can be added later as an additional provider.
- **[Trade-off] File-based state vs database** → `.skill.yaml` files are human-readable and git-friendly but not queryable. Acceptable for single-user desktop use. If multi-user needed, migrate to SQLite.

## Migration Plan

1. v1 `SkillService` and `SkillParser` are internal-only (no external API stability promise)
2. New `SkillSession` and `SkillStateMachine` replace them directly
3. Existing v1 skill sessions (if any) have no state files — treated as legacy, not migrated
4. No database migration needed (new tables are additive)

## Open Questions

- None remaining — all clarified during design exploration
