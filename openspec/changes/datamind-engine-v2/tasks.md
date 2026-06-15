# Tasks: datamind-engine-v2

## Phase 1: LLM Foundation

- [ ] **T1.1** — Implement `engine/llm.py`: `BaseLLMClient` abstract class, `OpenAIClient`, `OllamaClient` with chat completion, streaming, tool calling, retry (3x exponential backoff)
- [ ] **T1.2** — Extend `config.py` with LLM configuration: providers list, model definitions, `${ENV_VAR}` resolution, merge env vars with file config
- [ ] **T1.3** — Implement Ollama model auto-discovery: run `ollama list`, parse output, cache with TTL, fallback to manual config
- [ ] **T1.4** — Write tests for LLM client (mocked API responses, retry logic, streaming, env var resolution, Ollama list parsing)

## Phase 2: Prompt & Usage

- [ ] **T2.1** — Implement `engine/prompt.py`: `TemplateManager` loading markdown files from directory, YAML frontmatter parsing, `{{ variable }}` injection
- [ ] **T2.2** — Create 4 prompt templates: `data-scientist.md`, `code-reviewer.md`, `requirement-analyst.md`, `archivist.md`
- [ ] **T2.3** — Implement `engine/usage.py`: `UsageTracker` with per-session token counting, cost calculation, usage export
- [ ] **T2.4** — Write tests for prompt manager and usage tracker

## Phase 3: Skill State Machine

- [ ] **T3.1** — Implement `engine/skill_state.py`: `SkillStateMachine` with phase tracking, transition validation, `.skill.yaml` read/write
- [ ] **T3.2** — Implement `SkillSession` in `engine/skills.py`: session directory creation, artifact tracking, result recording
- [ ] **T3.3** — Rewrite `SkillParser` to support extended SKILL.md format with phase definitions
- [ ] **T3.4** — Write tests for state machine (transitions, validation, serialization, recovery)

## Phase 4: Agent Loop

- [ ] **T4.1** — Implement `engine/agent.py`: `DataMindAgent` loop (assemble context → render prompt → LLM call → execute tools → record decisions)
- [ ] **T4.2** — Implement GATE handling: pause execution, yield `WaitForApproval`, resume on human input
- [ ] **T4.3** — Implement tool definitions: bridge skills as LLM function calls, execute and return results
- [ ] **T4.4** — Write integration tests for agent loop (mock LLM, verify context assembly, tool execution, gate pause/resume)

## Phase 5: Skills Rewrite

- [ ] **T5.1** — Rewrite `skills/data-cleaning.md` with phase-based definition
- [ ] **T5.2** — Rewrite `skills/data-exploration.md` with phase-based definition
- [ ] **T5.3** — Rewrite `skills/feature-engineering.md` with phase-based definition
- [ ] **T5.4** — Rewrite `skills/model-training.md` with phase-based definition
- [ ] **T5.5** — Rewrite `skills/report-generation.md` with phase-based definition
- [ ] **T5.6** — Create `skills/requirement-discussion.md` (explore-context → propose-frame → gate-review → define-success → scope-analysis → gate-confirm)
- [ ] **T5.7** — Create `skills/auto-archive.md` (audit-artifacts → generate-summary → organize-outputs → gate-review-plan → execute-archive)

## Phase 6: L1-L3 Extensions

- [ ] **T6.1** — Implement materialized view rebuild in `engine/events.py`: read `executions/`, reconstruct dataset state
- [ ] **T6.2** — Implement reproducibility in `engine/lineage.py`: trace lineage to raw ancestors, replay script chain in order
- [ ] **T6.3** — Implement auto-refresh in `engine/assembly.py`: regenerate context files on state change triggers (dataset added, decision logged, execution completed)
- [ ] **T6.4** — Write tests for materialized view, reproducibility, and auto-refresh

## Phase 7: API & Integration

- [x] **T7.1** — Add SSE chat endpoint to `api/app.py`: streaming chat with agent loop, tool call progress events
- [x] **T7.2** — Add model listing and switching endpoints
- [x] **T7.3** — Add usage/cost query endpoint
- [x] **T7.4** — Update CLI `chat` command to use agent loop with streaming
- [x] **T7.5** — Update MCP server tools to integrate agent loop where applicable

## Phase 8: End-to-End Validation

- [x] **T8.1** — E2E test: full skill execution (data-cleaning) through all phases including gate pause/resume
- [x] **T8.2** — E2E test: interrupt/resume recovery — simulate context loss, verify AI can read `.skill.yaml` and continue
- [x] **T8.3** — Run full test suite, ensure 100% pass rate
