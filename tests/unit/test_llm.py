"""Tests for LLM configuration and env var resolution."""
import os
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
