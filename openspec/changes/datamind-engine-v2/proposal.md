# datamind-engine-v2

## Why

v1 established the four-layer engine (data lineage, cognitive journey, context assembly, skill system) — but the execution brain is missing. There's no LLM integration, no agent loop, and the skill system only parses definitions without executing them. Skills are linear JSON loops with no state machine, no interrupt/resume, no phase tracking. v2 turns the engine from a passive recorder into an active AI execution system.

## What Changes

### LLM Integration (new)
- LLM client abstraction supporting OpenAI-compatible APIs and Ollama local models
- Multi-model switching at runtime with auto-discovery of Ollama models via `ollama list`
- System prompt templates as markdown files in a directory, with variable injection
- Token usage and cost tracking aggregated per session
- LLM configuration via `.datamind/config.yaml` and environment variable injection (both supported)

### Agent Execution (new)
- Agent loop: assemble context → build prompt → call LLM → execute tools → record decisions
- Framework-agnostic LLM client design, reserving LangGraph migration path for v3
- Skill Session state machine: `.skill.yaml` lifecycle with phase tracking and artifact management
- Interrupt/resume: AI reads `.skill.yaml` and recovers to the exact phase, no re-execution needed

### Skill System — Major Rewrite
- All 7 skills rewritten with Comet-style phase definitions and state machine
- New skills: `requirement-discussion` (problem framing), `auto-archive` (project phase archival)
- Existing skills rewritten: `data-cleaning`, `data-exploration`, `feature-engineering`, `model-training`, `report-generation`
- `SkillSession` + `SkillStateMachine` replace v1's parse-only `SkillService`
- Each skill session produces timestamped artifact directories under `.datamind/skill-sessions/`

### L1-L3 Extensions
- Materialized view rebuild from `executions/` (event sourcing read path)
- Reproducibility: lineage traceback + script chain replay
- Context file auto-refresh on state change
- Chat SSE streaming endpoint in API

## Capabilities

### New Capabilities
- `llm-integration`: LLM client abstraction (OpenAI-compatible + Ollama), multi-model switching, prompt template management, usage tracking
- `agent-execution`: Agent loop orchestrating context → LLM → tools → decisions, skill session state machine with interrupt/resume, framework-agnostic for v3 LangGraph migration

### Modified Capabilities
- `data-lineage`: Add reproducibility (lineage traceback + script chain replay) and materialized view rebuild
- `context-assembly`: Add auto-refresh triggered by state changes
- `skill-system`: Replace parse-only SkillService with SkillSession + SkillStateMachine; phase-based skill definitions; `.skill.yaml` lifecycle management

## Impact

- **New modules**: `engine/llm.py`, `engine/prompt.py`, `engine/agent.py`, `engine/usage.py`, `engine/skill_state.py`
- **Extended modules**: `engine/skills.py` (rewrite), `engine/events.py`, `engine/lineage.py`, `engine/assembly.py`, `config.py`, `api/app.py`
- **New skills**: `skills/requirement-discussion.md`, `skills/auto-archive.md`
- **Rewritten skills**: `skills/data-cleaning.md`, `skills/data-exploration.md`, `skills/feature-engineering.md`, `skills/model-training.md`, `skills/report-generation.md`
- **Dependencies**: `ollama` (optional, for local model auto-discovery), `openai` Python SDK, `pyyaml`
- **Breaking**: `SkillService` and `SkillParser` public API replaced; skill execution flow changes
