# llm-integration Specification

## Purpose
TBD - created by archiving change datamind-engine-v2. Update Purpose after archive.
## Requirements
### Requirement: LLM Client Abstraction
The system SHALL provide a unified `BaseLLMClient` interface with concrete implementations for OpenAI-compatible APIs (`OpenAIClient`) and Ollama local models (`OllamaClient`). The `OpenAIClient` SHALL be verified against DeepSeek`s OpenAI-compatible API as a supported provider. All implementations SHALL support chat completion, streaming, and tool calling with retry on transient errors (429, 502, 503).

#### Scenario: DeepSeek V4 Flash via OpenAIClient
- **WHEN** the LLM client is configured with `provider: openai`, `api_base: https://api.deepseek.com`, `model: deepseek-v4-flash`
- **THEN** chat completion, streaming, and tool calling all work correctly via the `OpenAIClient`

#### Scenario: OpenAIClient works with any OpenAI-compatible provider
- **WHEN** the LLM client is configured with any OpenAI-compatible `api_base` and `model`
- **THEN** the `OpenAIClient` sends correctly formatted requests and parses responses, regardless of the specific provider

### Requirement: Multi-Model Switching
The system SHALL support switching between configured LLM models at runtime without restarting. The active model SHALL be specifiable per request or per session.

#### Scenario: Runtime model switch
- **WHEN** user selects a different model from the configured list
- **THEN** subsequent LLM calls use the newly selected model immediately

#### Scenario: Per-request model override
- **WHEN** agent specifies `model="deepseek-v3"` in a chat call
- **THEN** that single request uses deepseek-v3 regardless of the session default model

### Requirement: Ollama Model Auto-Discovery
When the Ollama provider is configured, the system SHALL automatically discover available models by running `ollama list`. The discovered model list SHALL be cached with a configurable TTL.

#### Scenario: Auto-discover models
- **WHEN** the system starts with Ollama provider enabled and `ollama list` returns models
- **THEN** the model list is populated from the command output and available for selection

#### Scenario: Ollama unavailable fallback
- **WHEN** `ollama list` fails (Ollama not installed or not running)
- **THEN** the system falls back to manually configured model names in `config.yaml`

### Requirement: LLM Configuration
The system SHALL load LLM configuration from `.datamind/config.yaml` with `${ENV_VAR}` environment variable injection. The configuration template SHALL include pre-configured provider entries for DeepSeek, OpenAI, and Ollama with their default `api_base` URLs and model lists.

#### Scenario: DeepSeek configured via config.yaml
- **WHEN** `.datamind/config.yaml` contains a `deepseek` provider entry with `api_base`, `api_key`, and `models`
- **THEN** the system creates an `OpenAIClient` pointed at the DeepSeek API

#### Scenario: Env var injection for API key
- **WHEN** the config contains `api_key: "${DEEPSEEK_API_KEY}"`
- **THEN** the value is resolved from the `DEEPSEEK_API_KEY` environment variable at load time

### Requirement: System Prompt Templates
The system SHALL load system prompt templates from a directory as markdown files with YAML frontmatter metadata. Templates SHALL support `{{ variable }}` injection for dynamic content including context manifest, skills list, datasets, and parameters.

#### Scenario: Load template
- **WHEN** agent requests the `data-scientist` template
- **THEN** the system reads `prompts/data-scientist.md`, parses YAML frontmatter, and returns the template with metadata

#### Scenario: Variable injection
- **WHEN** template contains `{{ context }}` and context manifest is provided
- **THEN** the rendered output replaces `{{ context }}` with the assembled context manifest content

#### Scenario: Missing template fallback
- **WHEN** requested template file does not exist
- **THEN** the system falls back to a built-in default system prompt

### Requirement: Usage Tracking
The system SHALL track token usage and cost for every LLM call, aggregated per skill session. Cost rates SHALL be configurable per model in `config.yaml`. Ollama local models SHALL track tokens with zero cost.

#### Scenario: Token counting
- **WHEN** an LLM call returns `usage: {prompt_tokens: 500, completion_tokens: 200}`
- **THEN** the session usage is incremented by 500 input and 200 output tokens

#### Scenario: Cost calculation
- **WHEN** a model has configured cost rates and tokens are tracked
- **THEN** the session cost is calculated as `(input_tokens * input_rate + output_tokens * output_rate) / 1000`

#### Scenario: Usage export
- **WHEN** agent requests session usage
- **THEN** the system returns total tokens, cost breakdown by model, and per-call history

