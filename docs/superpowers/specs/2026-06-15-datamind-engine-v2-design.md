---
comet_change: datamind-engine-v2
role: technical-design
canonical_spec: openspec
---

# DataMind Engine v2 — Technical Design

## Context

v1 established the four-layer engine: L1 Data Lineage (graph.db, describe, scripts), L2 Cognitive Journey (decisions, exploration, params, discoveries), L3 Context Assembly (priority-ordered context packing), L4 Skill System (SKILL.md parsing, AUTO/GATE step tracking). v1's skill system is parse-only — it reads SKILL.md files and tracks step state, but has no execution engine. There is no LLM integration, no agent loop, and skills cannot be interrupted and resumed efficiently.

v2 adds the execution brain: LLM clients, an agent loop, and a Comet-style skill state machine that enables fast interrupt/resume with minimal context re-reading.

## Architecture Overview

```
                         User Interface
                    CLI / API (SSE) / MCP
                              │
                    ┌─────────▼──────────┐
                    │    Agent Loop       │
                    │    engine/agent.py  │  ← v3 可替换为 LangGraph
                    │                    │
                    │  while not done:    │
                    │    assemble_context │
                    │    render_prompt    │
                    │    llm.chat(tools)  │
                    │    execute_tools    │
                    │    record_decisions │
                    └──┬───┬───┬───┬─────┘
                       │   │   │   │
          ┌────────────┘   │   │   └──────────────┐
          ▼                │   │                  ▼
   ┌─────────────┐        │   │         ┌──────────────────┐
   │ engine/llm  │        │   │         │ engine/          │
   │ BaseLLM     │        │   │         │ skill_state.py   │
   │ OpenAI      │        │   │         │ .skill.yaml      │
   │ Ollama      │        │   │         │ phase tracking   │
   └─────────────┘        │   │         └──────────────────┘
          │               │   │
   ┌──────┴──────┐       │   │
   │ prompt.py   │◄──────┘   │
   │ TemplateMgr │           │
   └─────────────┘           │
   ┌─────────────┐           │
   │ usage.py    │◄──────────┘
   │ UsageTracker│
   └─────────────┘
```

### Framework-Agnostic Boundary

```
┌─────────────────────────────────────────────┐
│  FRAMEWORK-AGNOSTIC (v3 不动)               │
│                                             │
│  engine/llm.py      LLM Client              │
│  engine/prompt.py   Prompt Templates        │
│  engine/usage.py    Usage Tracking          │
│                                             │
│  ┌─────────────────────┐                    │
│  │ engine/agent.py     │  ← v3 替换此模块   │
│  │ (custom loop)       │                    │
│  └─────────────────────┘                    │
│         ↕ v3 切换                           │
│  ┌─────────────────────┐                    │
│  │ LangGraph StateGraph │                    │
│  └─────────────────────┘                    │
└─────────────────────────────────────────────┘
```

## Key Decisions

### D1: LLM Client — Custom abstraction

**Choice**: Thin `BaseLLMClient` abstract class with `OpenAIClient` and `OllamaClient` implementations. No LangChain dependency.

**Why**: The OpenAI Python SDK already provides a clean interface. Ollama exposes an OpenAI-compatible endpoint. The abstraction is ~50 lines. LangChain adds 15+ dependencies for no value in a two-provider scenario.

**Alternatives**: LangChain LLM (too heavy), LiteLLM (proxy overkill for 2 providers)

### D2: Agent Loop — Custom lightweight, LangGraph-reserved

**Choice**: Custom while-loop (~120 lines) with interrupt/resume via `.skill.yaml`. Architecture reserves `engine/agent.py` as the replacement boundary for v3 LangGraph migration.

**Why**: v2's skill execution is linear (AUTO → GATE → AUTO → GATE). A custom loop is simpler and more transparent than LangGraph for linear flows. LangGraph's value (parallel execution, conditional branching, map-reduce) won't be needed until v3.

### D3: Skill State Machine — `.skill.yaml` as source of truth

**Choice**: Modeled after Comet's `.comet.yaml`. Each skill invocation creates `datamind/skill-sessions/<timestamp>-<target>/` containing `.skill.yaml` and phase artifacts. AI reads one ~200 byte file and knows the exact execution state.

**Why**: Fast resume is the killer feature. No re-reading SKILL.md, no parsing execution logs, no reconstructing state. Read `.skill.yaml` → see `phase: execute` → read `phase-2-strategy.md` → continue.

### D4: Prompt Templates — Directory of markdown files

**Choice**: `prompts/` directory with `.md` files. YAML frontmatter for metadata. `{{ variable }}` syntax for injection.

**Why**: Markdown is AI-native. Directory structure allows adding templates without code changes. No new format to learn.

### D5: Usage Tracking — Per-session aggregation

**Choice**: Token counts and costs stored in `.skill.yaml` under `usage:`. Cost rates configurable per model.

**Why**: Per-session granularity matches the skill session lifecycle. Ollama models track tokens at zero cost.

### D6: Ollama Discovery — `ollama list` auto-scan

**Choice**: Run `ollama list` on startup, cache with TTL, fall back to manual config.

**Why**: User pulls new Ollama models without updating config. Auto-discovery eliminates drift.

### D7: Config — Dual source (file + env vars)

**Choice**: `.datamind/config.yaml` with `${ENV_VAR}` injection. Env vars take precedence.

**Why**: Config file for documentation. Env vars for secrets. Standard 12-factor pattern.

## Skill State Machine Design

### `.skill.yaml` Schema

```yaml
skill: data-cleaning
target: sales.csv
session: 2026-06-15T143000Z-sales-cleaning
started_at: 2026-06-15T14:30:00Z
phase: execute

phases:
  analyze: complete
  propose-strategy: complete
  gate-approve: complete
  execute: in_progress
  validate: pending
  gate-result: pending

artifacts:
  analyze: phase-1-analyze.md
  propose-strategy: phase-2-strategy.md
  gate-approve: phase-3-gate.json

result: pending

usage:
  model: gpt-4o
  prompt_tokens: 3200
  completion_tokens: 1800
  cost: 0.023
```

### Resume Flow

```
AI context lost
    ↓
Read .skill.yaml (200 bytes)
    ↓
See: phase: execute, propose-strategy: complete
    ↓
Read: phase-2-strategy.md (the approved strategy)
    ↓
Continue from execute phase
    ↓
No re-execution of analyze + propose-strategy needed
```

## Skill Definitions

### Phase-Based SKILL.md Format

All 7 skills follow this format with Comet-style phase definitions:

```
requirement-discussion     auto-archive              data-cleaning
(6 phases)                (5 phases)                (6 phases)
─────────────────         ────────────              ────────────
explore-context (AUTO)    audit-artifacts (AUTO)    analyze (AUTO)
propose-frame (AUTO)      generate-summary (AUTO)   propose-strategy (AUTO)
gate-review (GATE)        organize-outputs (AUTO)   gate-approve (GATE)
define-success (AUTO)     gate-review-plan (GATE)   execute (AUTO)
scope-analysis (AUTO)     execute-archive (AUTO)    validate (AUTO)
gate-confirm (GATE)                                 gate-result (GATE)

data-exploration          feature-engineering       model-training
(4 phases)                (7 phases)                (6 phases)
──────────────            ──────────────────        ──────────────
read-describe (AUTO)      load-data (AUTO)          prepare-data (AUTO)
explore-patterns (AUTO)   analyze-features (AUTO)   select-models (AUTO)
generate-viz (AUTO)       propose-features (AUTO)   gate-model-choice (GATE)
gate-review (GATE)        gate-approve (GATE)       train (AUTO)
                          engineer-features (AUTO)  evaluate (AUTO)
                          validate (AUTO)           gate-results (GATE)
                          gate-result (GATE)

report-generation
(5 phases)
───────────────
load-findings (AUTO)
build-sections (AUTO)
gate-review-outline (GATE)
generate-report (AUTO)
gate-final-approval (GATE)
```

## Testing Strategy

| Layer | Approach | Coverage Target |
|-------|----------|-----------------|
| `engine/llm.py` | Mock API responses, test retry/streaming/config resolution | >90% |
| `engine/prompt.py` | Unit test template loading, variable injection, fallback | >90% |
| `engine/usage.py` | Unit test token counting, cost calculation, export | >90% |
| `engine/skill_state.py` | Unit test all transitions, validation, serialization, deserialization | >95% |
| `engine/skills.py` | Integration test: parse SKILL.md, initialize session, simulate phases | >85% |
| `engine/agent.py` | Integration test with mock LLM: AUTO execution, GATE pause/resume, tool dispatch | >85% |
| `engine/events.py` | Unit test rebuild from mock execution logs | >85% |
| `engine/lineage.py` | Integration test reproducibility with mock scripts | >85% |
| `engine/assembly.py` | Unit test auto-refresh triggers | >85% |
| E2E | Full skill execution (data-cleaning) + interrupt/resume recovery | 2 workflows |

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Custom agent loop insufficient for complex flows | Low (v3) | Architecture reserves `engine/agent.py` as replacement boundary |
| `.skill.yaml` schema evolution breaks old sessions | Medium | Version field + migration function; old sessions treated as legacy |
| Ollama API compatibility changes | Low | OpenAI-compatible endpoint is stable; fallback to manual config |
| Guard script Windows path bug blocks spec writes | Medium (workflow only) | Workaround via PowerShell; fix guard script separately |
