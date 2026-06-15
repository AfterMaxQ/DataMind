# llm-integration Specification

## Purpose
LLM client abstraction layer supporting OpenAI-compatible APIs and Ollama local models, with multi-model switching, prompt template management, and usage tracking.

## ADDED Requirements

### Requirement: LLM Client Abstraction
The system SHALL provide a unified LLM client interface (`BaseLLMClient`) with concrete implementations for OpenAI-compatible APIs (`OpenAIClient`) and Ollama local models (`OllamaClient`). All clients SHALL support chat completion, streaming responses, and tool calling through a common interface.

#### Scenario: OpenAI chat completion
- **WHEN** agent calls `llm.chat(messages=[...], tools=[...])` with provider configured as `openai`
- **THEN** the request is sent to the configured OpenAI-compatible endpoint and the response is returned with text content and any tool calls

#### Scenario: Ollama chat completion
- **WHEN** agent calls `llm.chat(messages=[...])` with provider configured as `ollama`
- **THEN** the request is sent to the local Ollama endpoint (`http://localhost:11434/v1`) and the response is returned

#### Scenario: Streaming response
- **WHEN** agent calls `llm.chat(messages=[...], stream=True)`
- **THEN** the method yields response chunks as they arrive, enabling real-time display

#### Scenario: API error retry
- **WHEN** an API call fails with a transient error (429, 502, 503)
- **THEN** the client retries up to 3 times with exponential backoff before raising an error

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
The system SHALL load LLM configuration from `.datamind/config.yaml` with support for `${ENV_VAR}` environment variable injection. Environment variables SHALL take precedence over file values.

#### Scenario: Config with env var
- **WHEN** config contains `api_key: ${OPENAI_API_KEY}` and the environment variable is set
- **THEN** the resolved value uses the environment variable

#### Scenario: Config file only
- **WHEN** config contains a plain value like `api_url: https://api.openai.com/v1`
- **THEN** the value is used as-is from the config file

#### Scenario: Env var override
- **WHEN** both config file and environment variable specify the same key
- **THEN** the environment variable value takes precedence

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
