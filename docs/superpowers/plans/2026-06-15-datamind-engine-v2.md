---
archived-with: 2026-06-15-datamind-engine-v2
status: final
---
﻿---
change: datamind-engine-v2
design-doc: docs/superpowers/specs/2026-06-15-datamind-engine-v2-design.md
base-ref: 2808165382b9928d6e386bbe789fb4de46b896c7
---

# DataMind Engine v2 Implementation Plan

**Goal:** Add LLM-powered agent execution (LLM clients, agent loop, Comet-style skill state machine with interrupt/resume) and extend L1-L3 layers (materialized view rebuild, reproducibility, auto-refresh) to DataMind Studio.

**Architecture:** Strict dependency order: LLM foundation → Prompt & Usage → Skill State Machine → Agent Loop → Skills Rewrite → L1-L3 Extensions → API/CLI/MCP Integration → E2E Validation. Framework-agnostic boundary ensures `engine/llm.py`, `engine/prompt.py`, `engine/usage.py` remain stable through v3 LangGraph migration.

---

## Phase 1: LLM Foundation

- [x] **T1.1** — Add `openai>=1.0` and `sse-starlette>=1.8` to pyproject.toml, install dependencies
- [x] **T1.2** — Extend `config.py`: LLM constants, `resolve_env_vars()`, `load_llm_config()` with `${ENV_VAR}` support and env var overrides
- [x] **T1.3** — Implement `engine/llm.py`: `BaseLLMClient` abstract class, `OpenAIClient` (chat, stream, retry, tool calling), `OllamaClient` (auto-discovery, cache, fallback)
- [x] **T1.4** — Write `tests/unit/test_llm.py`: 24 tests covering config resolution, chat, streaming, retry, tool calls, Ollama discovery

## Phase 2: Prompt & Usage

- [x] **T2.1** — Implement `engine/prompt.py`: `TemplateManager` with markdown loading, YAML frontmatter parsing, `{{ variable }}` injection, default fallback
- [x] **T2.2** — Create 4 prompt templates: `data-scientist.md`, `code-reviewer.md`, `requirement-analyst.md`, `archivist.md`
- [x] **T2.3** — Implement `engine/usage.py`: `UsageTracker` with per-session token counting, cost calculation, export
- [x] **T2.4** — Write `tests/unit/test_prompt.py` (6 tests) and `tests/unit/test_usage.py` (7 tests)

## Phase 3: Skill State Machine

- [x] **T3.1** — Implement `engine/skill_state.py`: `SkillPhase`, `SkillSessionState`, `SkillStateMachine` with phase tracking, transition validation, `.skill.yaml` R/W
- [x] **T3.2** — Extend `engine/skills.py`: `SkillPhase` dataclass, `SkillParser` v2 (phase extraction), `SkillSession` manager (directory creation, artifact recording, resume)
- [x] **T3.3** — Write `tests/unit/test_skill_state.py` (11 tests) and extend `tests/unit/test_skills.py` (6 new tests)

## Phase 4: Agent Loop

- [x] **T4.1** — Implement `engine/agent.py`: `DataMindAgent` loop (context → prompt → LLM → tools → decisions), GATE pause/resume, tool dispatch
- [x] **T4.2** — Write `tests/integration/test_agent.py` with `MockLLMClient`: AUTO execution, GATE pause/resume, tool calls, context assembly, usage tracking

## Phase 5: Skills Rewrite

- [x] **T5.1** — Rewrite `skills/data-cleaning.md` (6 phases)
- [x] **T5.2** — Rewrite `skills/data-exploration.md` (4 phases)
- [x] **T5.3** — Rewrite `skills/feature-engineering.md` (7 phases)
- [x] **T5.4** — Rewrite `skills/model-training.md` (6 phases)
- [x] **T5.5** — Rewrite `skills/report-generation.md` (5 phases)
- [x] **T5.6** — Create `skills/requirement-discussion.md` (6 phases)
- [x] **T5.7** — Create `skills/auto-archive.md` (5 phases)

## Phase 6: L1-L3 Extensions

- [x] **T6.1** — Add `list_all()` to `engine/events.py` `ExecutionLog` for materialized view rebuild
- [x] **T6.2** — Add `reproduce()` to `engine/lineage.py` `LineageService` for script chain replay
- [x] **T6.3** — Add `AutoRefreshTrigger` to `engine/assembly.py` for context file auto-regeneration
- [x] **T6.4** — Write tests for materialized view, reproducibility, and auto-refresh

## Phase 7: API & Integration

- [x] **T7.1** — Wire new services into `engine/project.py` facade (llm_client, prompt_manager)
- [x] **T7.2** — Add SSE chat endpoint to `api/app.py` + model list/switch + skill session + usage endpoints
- [x] **T7.3** — Add `chat` command to `cli/main.py` with streaming and skill interaction
- [x] **T7.4** — Add agent MCP tools to `mcp/server.py` (execute_skill, list_models)

## Phase 8: End-to-End Validation

- [x] **T8.1** — E2E test: full skill execution (data-cleaning) through all phases with MockLLMClient
- [x] **T8.2** — E2E test: interrupt/resume recovery — simulate context loss, verify `.skill.yaml` read and continue
- [x] **T8.3** — Run full test suite, ensure 100% pass rate

---

## Dependency Graph

```
Phase 1 ──→ Phase 2 ──→ Phase 4 ──→ Phase 5 ──→ Phase 7 ──→ Phase 8
    │                                    │
    └──→ Phase 3 ────────────────────────┘
              │
Phase 6 ──────┘ (independent)
```
