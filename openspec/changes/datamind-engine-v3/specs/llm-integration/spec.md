## MODIFIED Requirements

### Requirement: LLM Client Abstraction
The system SHALL provide a unified `BaseLLMClient` interface with concrete implementations for OpenAI-compatible APIs (`OpenAIClient`) and Ollama local models (`OllamaClient`). The `OpenAIClient` SHALL be verified against DeepSeek`s OpenAI-compatible API as a supported provider. All implementations SHALL support chat completion, streaming, and tool calling with retry on transient errors (429, 502, 503).

#### Scenario: DeepSeek V4 Flash via OpenAIClient
- **WHEN** the LLM client is configured with `provider: openai`, `api_base: https://api.deepseek.com`, `model: deepseek-v4-flash`
- **THEN** chat completion, streaming, and tool calling all work correctly via the `OpenAIClient`

#### Scenario: OpenAIClient works with any OpenAI-compatible provider
- **WHEN** the LLM client is configured with any OpenAI-compatible `api_base` and `model`
- **THEN** the `OpenAIClient` sends correctly formatted requests and parses responses, regardless of the specific provider

### Requirement: LLM Configuration
The system SHALL load LLM configuration from `.datamind/config.yaml` with `${ENV_VAR}` environment variable injection. The configuration template SHALL include pre-configured provider entries for DeepSeek, OpenAI, and Ollama with their default `api_base` URLs and model lists.

#### Scenario: DeepSeek configured via config.yaml
- **WHEN** `.datamind/config.yaml` contains a `deepseek` provider entry with `api_base`, `api_key`, and `models`
- **THEN** the system creates an `OpenAIClient` pointed at the DeepSeek API

#### Scenario: Env var injection for API key
- **WHEN** the config contains `api_key: "${DEEPSEEK_API_KEY}"`
- **THEN** the value is resolved from the `DEEPSEEK_API_KEY` environment variable at load time
