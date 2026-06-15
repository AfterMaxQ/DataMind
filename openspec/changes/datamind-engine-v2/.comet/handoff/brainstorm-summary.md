# Brainstorm Summary

- Change: datamind-engine-v2
- Date: 2026-06-15

## Confirmed Technical Approach

Custom lightweight architecture with 6 new modules (llm, prompt, agent, usage, skill_state, skills rewrite) and 5 extended modules (events, lineage, assembly, config, api). LLM client layer is framework-agnostic; agent loop is replaceable for v3 LangGraph migration.

7 architecture decisions confirmed: D1 (custom LLM client), D2 (custom agent loop + LangGraph reserved), D3 (.skill.yaml state machine), D4 (markdown prompt templates), D5 (per-session usage tracking), D6 (ollama list auto-discovery), D7 (config.yaml + env var injection).

## Key Trade-offs and Risks

- Custom agent loop simpler than LangGraph for v2 linear flows, but may need rewrite in v3
- .skill.yaml file-based state is human-readable but not queryable at scale
- 2 providers (OpenAI-compatible + Ollama) vs 100+ with LiteLLM
- Ollama auto-discovery graceful degradation if ollama not installed

## Testing Strategy

- Unit tests: llm (mock API), prompt, usage, skill_state (95%+ coverage)
- Integration tests: agent loop with mock LLM, skills with real parser
- E2E: full data-cleaning execution + interrupt/resume recovery

## Spec Patches

5 delta specs created:
- llm-integration (6 ADDED requirements)
- agent-execution (5 ADDED requirements)
- data-lineage (2 ADDED requirements)
- context-assembly (1 ADDED requirement)
- skill-system (3 ADDED + 3 MODIFIED requirements)
