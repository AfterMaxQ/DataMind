"""Tests for LLM configuration and env var resolution."""
import os
import subprocess
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
import yaml

from datamind.config import (
    resolve_env_vars,
    load_llm_config,
    LLM_DEFAULT_MODEL,
    LLM_MAX_RETRIES,
    LLM_RETRYABLE_STATUSES,
    LLM_DEFAULT_TIMEOUT,
    LLM_DEFAULT_API_BASE,
)
from datamind.engine.llm import (
    LLMResponse,
    BaseLLMClient,
    OpenAIClient,
    OllamaClient,
)


# ---------------------------------------------------------------------------
# resolve_env_vars tests
# ---------------------------------------------------------------------------

def test_resolve_env_vars_replaces_dollar_brace():
    """${ENV_VAR} references are replaced with the env var value."""
    os.environ["DATAMIND_TEST_VAR"] = "resolved_value"
    try:
        result = resolve_env_vars({"key": "${DATAMIND_TEST_VAR}"})
        assert result["key"] == "resolved_value"
    finally:
        del os.environ["DATAMIND_TEST_VAR"]


def test_resolve_env_vars_missing_var_left_unchanged():
    """Unresolvable ${ENV_VAR} references are left as-is."""
    result = resolve_env_vars({"key": "${DATAMIND_NONEXISTENT_VAR_XYZ}"})
    assert result["key"] == "${DATAMIND_NONEXISTENT_VAR_XYZ}"


def test_resolve_env_vars_nested_dict():
    """Env vars are resolved recursively inside nested dicts."""
    os.environ["DATAMIND_TEST_NESTED"] = "nested_val"
    try:
        result = resolve_env_vars({
            "outer": {
                "inner": "${DATAMIND_TEST_NESTED}"
            }
        })
        assert result["outer"]["inner"] == "nested_val"
    finally:
        del os.environ["DATAMIND_TEST_NESTED"]


def test_resolve_env_vars_nested_list():
    """Env vars are resolved inside lists recursively."""
    os.environ["DATAMIND_TEST_LIST"] = "list_val"
    try:
        result = resolve_env_vars({
            "items": ["${DATAMIND_TEST_LIST}", "static"]
        })
        assert result["items"] == ["list_val", "static"]
    finally:
        del os.environ["DATAMIND_TEST_LIST"]


def test_resolve_env_vars_non_string_types():
    """Non-string values (int, float, bool, None) pass through unchanged."""
    result = resolve_env_vars({
        "count": 42,
        "pi": 3.14,
        "flag": True,
        "nothing": None,
    })
    assert result["count"] == 42
    assert result["pi"] == 3.14
    assert result["flag"] is True
    assert result["nothing"] is None


# ---------------------------------------------------------------------------
# load_llm_config tests
# ---------------------------------------------------------------------------

def test_load_llm_config_from_file(tmp_project):
    """load_llm_config loads and resolves a YAML config file."""
    dot = tmp_project / ".datamind"
    dot.mkdir()
    config_path = dot / "config.yaml"
    config_path.write_text(yaml.dump({
        "model": "gpt-4o-mini",
        "provider": "openai",
        "api_key": "${DATAMIND_TEST_API_KEY}",
        "max_retries": 5,
    }))

    os.environ["DATAMIND_TEST_API_KEY"] = "sk-test-123"
    try:
        config = load_llm_config(str(config_path))
        assert config["model"] == "gpt-4o-mini"
        assert config["provider"] == "openai"
        assert config["api_key"] == "sk-test-123"
        assert config["max_retries"] == 5
    finally:
        del os.environ["DATAMIND_TEST_API_KEY"]


def test_load_llm_config_env_var_override(tmp_project):
    """Env vars (DATAMIND_MODEL, etc.) take precedence over config file."""
    dot = tmp_project / ".datamind"
    dot.mkdir()
    config_path = dot / "config.yaml"
    config_path.write_text(yaml.dump({
        "model": "gpt-4o",
        "provider": "openai",
        "max_retries": 3,
    }))

    os.environ["DATAMIND_MODEL"] = "deepseek-v3"
    os.environ["DATAMIND_PROVIDER"] = "ollama"
    os.environ["DATAMIND_MAX_RETRIES"] = "10"
    try:
        config = load_llm_config(str(config_path))
        assert config["model"] == "deepseek-v3"
        assert config["provider"] == "ollama"
        assert config["max_retries"] == 10
    finally:
        del os.environ["DATAMIND_MODEL"]
        del os.environ["DATAMIND_PROVIDER"]
        del os.environ["DATAMIND_MAX_RETRIES"]


def test_load_llm_config_file_not_found_returns_defaults():
    """When the config file does not exist, return sensible defaults."""
    config = load_llm_config("/nonexistent/path/config.yaml")
    assert config["model"] == LLM_DEFAULT_MODEL
    assert config["provider"] == "openai"
    assert config["max_retries"] == LLM_MAX_RETRIES
    assert config["timeout"] == LLM_DEFAULT_TIMEOUT
    assert config["api_base"] == LLM_DEFAULT_API_BASE
    assert "retryable_statuses" in config


def test_load_llm_config_empty_file(tmp_project):
    """An empty config file returns defaults."""
    dot = tmp_project / ".datamind"
    dot.mkdir()
    config_path = dot / "config.yaml"
    config_path.write_text("")

    config = load_llm_config(str(config_path))
    assert config["model"] == LLM_DEFAULT_MODEL


def test_load_llm_config_partial_override(tmp_project):
    """Only specified env var overrides change; other config values preserved."""
    dot = tmp_project / ".datamind"
    dot.mkdir()
    config_path = dot / "config.yaml"
    config_path.write_text(yaml.dump({
        "model": "gpt-4o",
        "provider": "openai",
        "timeout": 90,
    }))

    os.environ["DATAMIND_MODEL"] = "claude-sonnet"
    try:
        config = load_llm_config(str(config_path))
        assert config["model"] == "claude-sonnet"
        assert config["provider"] == "openai"  # unchanged
        assert config["timeout"] == 90  # from file
    finally:
        del os.environ["DATAMIND_MODEL"]


# ---------------------------------------------------------------------------
# LLMResponse tests
# ---------------------------------------------------------------------------

def test_llm_response_defaults():
    """LLMResponse has sensible defaults for all fields."""
    r = LLMResponse()
    assert r.content == ""
    assert r.tool_calls == []
    assert r.usage == {}
    assert r.model == ""
    assert r.finish_reason == "stop"


def test_llm_response_field_assignment():
    """LLMResponse fields are assignable."""
    r = LLMResponse(
        content="Hello",
        tool_calls=[{"name": "search", "arguments": {"q": "test"}}],
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        model="gpt-4o",
        finish_reason="tool_calls",
    )
    assert r.content == "Hello"
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0]["name"] == "search"
    assert r.usage["prompt_tokens"] == 10
    assert r.model == "gpt-4o"
    assert r.finish_reason == "tool_calls"


# ---------------------------------------------------------------------------
# BaseLLMClient tests
# ---------------------------------------------------------------------------

def test_base_llm_client_is_abstract():
    """BaseLLMClient cannot be instantiated directly — it is abstract."""
    with pytest.raises(TypeError):
        BaseLLMClient(model="test-model")  # type: ignore[abstract]


def test_openai_client_inherits_base():
    """OpenAIClient is a subclass of BaseLLMClient."""
    client = OpenAIClient(api_key="sk-test", model="gpt-4o")
    assert isinstance(client, BaseLLMClient)


def test_ollama_client_inherits_base():
    """OllamaClient is a subclass of BaseLLMClient."""
    client = OllamaClient(model="llama3")
    assert isinstance(client, BaseLLMClient)


# ---------------------------------------------------------------------------
# OpenAIClient tests
# ---------------------------------------------------------------------------

def _make_chunk(content=None, role=None, delta_tool_calls=None, finish_reason=None):
    """Build a minimal fake OpenAI completion chunk object."""
    chunk = MagicMock()
    choices_item = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = delta_tool_calls or []
    delta.role = role
    choices_item.delta = delta
    choices_item.finish_reason = finish_reason
    chunk.choices = [choices_item]
    chunk.model = "gpt-4o"
    chunk.usage = None
    return chunk


def test_openai_chat_returns_response():
    """chat() returns an LLMResponse when the API returns a non-stream response."""
    client = OpenAIClient(api_key="sk-test", model="gpt-4o", max_retries=1)
    fake_choice = MagicMock()
    fake_message = MagicMock()
    fake_message.content = "Hello from OpenAI"
    fake_message.tool_calls = None
    fake_choice.message = fake_message
    fake_choice.finish_reason = "stop"
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_response.model = "gpt-4o"
    fake_response.usage = MagicMock(prompt_tokens=5, completion_tokens=10, total_tokens=15)

    client._client = MagicMock()
    client._client.chat.completions.create.return_value = fake_response

    result = client.chat(messages=[{"role": "user", "content": "Hi"}])
    assert isinstance(result, LLMResponse)
    assert result.content == "Hello from OpenAI"
    assert result.model == "gpt-4o"
    assert result.usage["prompt_tokens"] == 5
    assert result.usage["completion_tokens"] == 10
    assert result.finish_reason == "stop"


def test_openai_streaming_yields_chunks():
    """chat(stream=True) yields LLMResponse objects for each chunk."""
    client = OpenAIClient(api_key="sk-test", model="gpt-4o", max_retries=1)

    chunks = [
        _make_chunk(content=None, role="assistant"),
        _make_chunk(content="Hello "),
        _make_chunk(content="world"),
        _make_chunk(content=None, finish_reason="stop"),
    ]
    client._client = MagicMock()
    client._client.chat.completions.create.return_value = chunks

    results = list(client.chat(messages=[{"role": "user", "content": "Hi"}], stream=True))
    assert len(results) > 0
    # Final assembled content should contain all delta text
    content_parts = [r.content for r in results if r.content]
    combined = "".join(content_parts)
    assert "Hello" in combined


def test_openai_retry_on_429():
    """chat() retries on 429 status with exponential backoff."""
    import openai

    client = OpenAIClient(api_key="sk-test", model="gpt-4o", max_retries=3)

    mock_response = MagicMock()
    mock_response.status_code = 429
    api_error_429 = openai.APIStatusError(
        message="Rate limited",
        response=mock_response,
        body={"error": {"message": "Rate limited"}},
    )
    api_error_429.status_code = 429

    mock_success = MagicMock()
    fake_choice = MagicMock()
    fake_message = MagicMock()
    fake_message.content = "Retry success"
    fake_message.tool_calls = None
    fake_choice.message = fake_message
    fake_choice.finish_reason = "stop"
    mock_success.choices = [fake_choice]
    mock_success.model = "gpt-4o"
    mock_success.usage = MagicMock(prompt_tokens=1, completion_tokens=2, total_tokens=3)

    client._client = MagicMock()
    client._client.chat.completions.create.side_effect = [
        api_error_429,
        mock_success,
    ]

    with patch("time.sleep", return_value=None) as mock_sleep:
        result = client.chat(messages=[{"role": "user", "content": "Hi"}])
        assert mock_sleep.call_count == 1
        assert result.content == "Retry success"


def test_openai_exhausts_retries_raises():
    """chat() raises after exhausting all retries on retryable errors."""
    client = OpenAIClient(api_key="sk-test", model="gpt-4o", max_retries=2)

    import openai
    mock_response = MagicMock()
    mock_response.status_code = 429
    api_error_429 = openai.APIStatusError(
        message="Rate limited",
        response=mock_response,
        body={"error": {"message": "Rate limited"}},
    )
    api_error_429.status_code = 429

    client._client = MagicMock()
    client._client.chat.completions.create.side_effect = api_error_429

    with patch("time.sleep", return_value=None):
        with pytest.raises(openai.APIStatusError):
            client.chat(messages=[{"role": "user", "content": "Hi"}])


def test_openai_tool_calling():
    """chat() extracts tool_calls from the API response message."""
    client = OpenAIClient(api_key="sk-test", model="gpt-4o", max_retries=1)

    fake_tool_call = MagicMock()
    fake_tool_call.id = "call_123"
    fake_tool_call.type = "function"
    fake_tool_call.function = MagicMock()
    fake_tool_call.function.name = "search"
    fake_tool_call.function.arguments = '{"q": "test"}'

    fake_choice = MagicMock()
    fake_message = MagicMock()
    fake_message.content = None
    fake_message.tool_calls = [fake_tool_call]
    fake_choice.message = fake_message
    fake_choice.finish_reason = "tool_calls"

    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_response.model = "gpt-4o"
    fake_response.usage = MagicMock(prompt_tokens=20, completion_tokens=30, total_tokens=50)

    client._client = MagicMock()
    client._client.chat.completions.create.return_value = fake_response

    result = client.chat(messages=[{"role": "user", "content": "Search for test"}])
    assert result.finish_reason == "tool_calls"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "search"
    assert result.tool_calls[0]["arguments"] == '{"q": "test"}'


def test_openai_lazy_client_init():
    """The OpenAI client is lazily initialized on first use, not at __init__."""
    client = OpenAIClient(api_key="sk-test", model="gpt-4o")
    assert client._client is None  # Not initialized yet

    # Patch the _get_client method to inject a mock without calling real OpenAI
    mock_client = MagicMock()
    fake_choice = MagicMock()
    fake_message = MagicMock()
    fake_message.content = "lazy"
    fake_message.tool_calls = None
    fake_choice.message = fake_message
    fake_choice.finish_reason = "stop"

    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_response.model = "gpt-4o"
    fake_response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)

    mock_client.chat.completions.create.return_value = fake_response

    with patch.object(client, "_get_client", return_value=mock_client) as mock_get_client:
        result = client.chat(messages=[{"role": "user", "content": "Hi"}])
        assert result.content == "lazy"
        assert mock_get_client.call_count == 1



# ---------------------------------------------------------------------------
# OllamaClient tests
# ---------------------------------------------------------------------------

OLLAMA_LIST_OUTPUT = """NAME                     ID              SIZE      MODIFIED
llama3:latest            1234abcd5678    4.7 GB    2 days ago
mistral:latest           abcd12345678    4.1 GB    5 days ago
codellama:7b             efgh98765432    3.8 GB    1 week ago
"""


def test_ollama_client_default_config():
    """OllamaClient uses the default api_url when none is provided."""
    client = OllamaClient(model="llama3")
    assert client.api_url == "http://localhost:11434/v1"
    assert client.model == "llama3"
    assert client.auto_discover is True
    assert client.discovery_ttl == 300
    assert client.manual_models == []


def test_ollama_list_models_parses_output():
    """_discover_models() parses 'ollama list' output into model names."""
    client = OllamaClient(model="llama3", auto_discover=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=OLLAMA_LIST_OUTPUT,
            stderr="",
            returncode=0,
        )
        models = client._discover_models()
        mock_run.assert_called_once_with(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert "llama3:latest" in models
        assert "mistral:latest" in models
        assert "codellama:7b" in models
        assert len(models) == 3


def test_ollama_list_models_fallback_on_error():
    """list_models() falls back to manual_models on subprocess error."""
    client = OllamaClient(
        model="llama3",
        auto_discover=True,
        manual_models=["fallback-model"],
    )
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ollama list", timeout=10)
        models = client.list_models()
        assert models == ["fallback-model"]


def test_ollama_discovery_cache():
    """Second call to list_models() uses cached result, not re-running subprocess."""
    client = OllamaClient(model="llama3", auto_discover=True, discovery_ttl=9999)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=OLLAMA_LIST_OUTPUT,
            stderr="",
            returncode=0,
        )
        first = client.list_models()
        second = client.list_models()
        # subprocess.run should only be called once (cached)
        assert mock_run.call_count == 1
        assert first == second


def test_ollama_discovery_disabled_returns_manual():
    """When auto_discover is False, list_models() returns manual_models only."""
    client = OllamaClient(
        model="llama3",
        auto_discover=False,
        manual_models=["custom-model-1", "custom-model-2"],
    )
    models = client.list_models()
    assert models == ["custom-model-1", "custom-model-2"]


def test_ollama_chat_delegates_to_openai_compatible():
    """OllamaClient.chat() delegates to an OpenAI-compatible endpoint."""
    client = OllamaClient(model="llama3", manual_models=["llama3"])

    fake_choice = MagicMock()
    fake_message = MagicMock()
    fake_message.content = "Ollama response"
    fake_message.tool_calls = None
    fake_choice.message = fake_message
    fake_choice.finish_reason = "stop"
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_response.model = "llama3"
    fake_response.usage = MagicMock(prompt_tokens=3, completion_tokens=6, total_tokens=9)

    client._client = MagicMock()
    client._client.chat.completions.create.return_value = fake_response

    result = client.chat(messages=[{"role": "user", "content": "Hello"}])
    assert isinstance(result, LLMResponse)
    assert result.content == "Ollama response"
    assert result.model == "llama3"
