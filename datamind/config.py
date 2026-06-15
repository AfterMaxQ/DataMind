"""Configuration constants and project defaults."""

from pathlib import Path

# Default directory names inside .datamind/
GRAPH_DB_NAME = "graph.db"
CONTEXT_DIR = "context"
CONFIG_FILE = "config.yaml"

# Context file names
PROJECT_MD = "PROJECT.md"
DATASETS_MD = "DATASETS.md"
HISTORY_MD = "HISTORY.md"
EXPLORATION_MD = "EXPLORATION.md"
PARAMS_MD = "PARAMS.md"
CHECKPOINT_MD = "CHECKPOINT.md"
CONTEXT_MANIFEST_MD = "CONTEXT_MANIFEST.md"

# Data directories (sibling to .datamind/)
DATA_DIR = "data"
RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"
SCRIPTS_DIR = "scripts"
DESCRIBE_DIR = "describe"
EXECUTIONS_DIR = "executions"
SKILLS_DIR = "skills"

# Cognitive journey files
DECISIONS_FILE = "decisions.jsonl"
EXPLORATION_FILE = "exploration.json"
PARAMS_FILE = "params.json"
DISCOVERIES_FILE = "discoveries.jsonl"

# Context packing priorities (token allocations)
TOKEN_BUDGET = 40_000
PRIORITY1_TOKENS = 2_500
PRIORITY2_TOKENS = 8_000
PRIORITY3_TOKENS = 3_000
PRIORITY4_TOKENS = 2_000

# Checkpoint: regenerate after N new execution logs
CHECKPOINT_THRESHOLD = 10

# Supported data formats for auto-describe
SUPPORTED_FORMATS = {".csv", ".parquet", ".xlsx", ".xls", ".json", ".tsv"}

# SQLite pragmas for initialization
SQLITE_PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
]


def resolve_dot_datamind(project_root: str | Path) -> Path:
    """Resolve the .datamind/ directory path from a project root."""
    root = Path(project_root).resolve()
    return root / ".datamind"


def resolve_component_paths(project_root: str | Path) -> dict[str, Path]:
    """Resolve all .datamind/ component paths for a project root."""
    base = resolve_dot_datamind(project_root)
    root = Path(project_root).resolve()
    return {
        "graph_db": base / GRAPH_DB_NAME,
        "context_dir": base / CONTEXT_DIR,
        "config_file": base / CONFIG_FILE,
        "data_dir": root / DATA_DIR,
        "raw_data": root / RAW_DATA_DIR,
        "processed_data": root / PROCESSED_DATA_DIR,
        "scripts_dir": root / SCRIPTS_DIR,
        "describe_dir": root / DESCRIBE_DIR,
        "executions_dir": root / EXECUTIONS_DIR,
        "skills_dir": root / SKILLS_DIR,
        "decisions_file": base / DECISIONS_FILE,
        "exploration_file": base / EXPLORATION_FILE,
        "params_file": base / PARAMS_FILE,
        "discoveries_file": base / DISCOVERIES_FILE,
    }


def initialize_project(project_root: str | Path, config: dict | None = None) -> dict[str, Path]:
    """Initialize a DataMind project directory structure.

    Creates .datamind/ and all required subdirectories. Returns the
    resolved component paths dict.
    """
    root = Path(project_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Project root does not exist: {root}")

    paths = resolve_component_paths(project_root)
    base = paths["graph_db"].parent  # .datamind/
    base.mkdir(parents=True, exist_ok=True)

    # Create all directories
    for key, path_obj in paths.items():
        if key.endswith("_dir") or key.endswith("_data") or key in ("scripts_dir", "describe_dir", "executions_dir", "skills_dir", "context_dir"):
            path_obj.mkdir(parents=True, exist_ok=True)

    # Write default config.yaml if config provided
    if config is not None:
        import yaml
        with open(paths["config_file"], "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

    return paths


# ---------------------------------------------------------------------------
# LLM configuration constants
# ---------------------------------------------------------------------------

LLM_DEFAULT_MODEL = "gpt-4o"
LLM_DEFAULT_PROVIDER = "openai"
LLM_MAX_RETRIES = 3
LLM_DEFAULT_TIMEOUT = 60
LLM_DEFAULT_API_BASE = "https://api.openai.com/v1"
LLM_RETRYABLE_STATUSES = {429, 502, 503, 504}


# ---------------------------------------------------------------------------
# Environment variable resolution
# ---------------------------------------------------------------------------

import re as _re
import os as _os

_ENV_VAR_PATTERN = _re.compile(r"\$\{(\w+)\}")


def resolve_env_vars(config: dict) -> dict:
    """Recursively resolve ``${ENV_VAR}`` references in dicts, lists, and strings.

    Strings that match ``${NAME}`` are replaced with the value of the
    environment variable *NAME* if it exists.  Unresolvable references are
    left unchanged.
    """
    return _resolve_value(config)


def _resolve_value(value):
    """Resolve a single value (str, dict, list, or scalar)."""
    if isinstance(value, str):
        return _resolve_string(value)
    if isinstance(value, dict):
        return {k: _resolve_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item) for item in value]
    return value


def _resolve_string(text: str) -> str:
    """Replace all ``${ENV_VAR}`` patterns in *text* with their values."""
    def _replacer(match):
        name = match.group(1)
        return _os.environ.get(name, match.group(0))
    return _ENV_VAR_PATTERN.sub(_replacer, text)


# ---------------------------------------------------------------------------
# LLM config loading
# ---------------------------------------------------------------------------

def load_llm_config(config_path: str) -> dict:
    """Load LLM configuration from a YAML file.

    1. Reads the file at *config_path* (if it exists).
    2. Resolves ``${ENV_VAR}`` references via :func:`resolve_env_vars`.
    3. Applies environment-variable overrides (highest precedence):

       ===================== ===============
       Env variable          Config key
       ===================== ===============
       ``DATAMIND_MODEL``    ``model``
       ``DATAMIND_PROVIDER`` ``provider``
       ``DATAMIND_MAX_RETRIES`` ``max_retries``
       ===================== ===============

    Returns a config dict with defaults filled in for any missing keys.
    """
    config: dict = {}
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
        if isinstance(loaded, dict):
            config = loaded
    except FileNotFoundError:
        pass

    config = resolve_env_vars(config)

    # Apply env-var overrides
    env_model = _os.environ.get("DATAMIND_MODEL")
    if env_model:
        config["model"] = env_model

    env_provider = _os.environ.get("DATAMIND_PROVIDER")
    if env_provider:
        config["provider"] = env_provider

    env_max_retries = _os.environ.get("DATAMIND_MAX_RETRIES")
    if env_max_retries:
        try:
            config["max_retries"] = int(env_max_retries)
        except ValueError:
            pass

    # Fill in defaults for missing keys
    config.setdefault("model", LLM_DEFAULT_MODEL)
    config.setdefault("provider", LLM_DEFAULT_PROVIDER)
    config.setdefault("api_key", None)
    config.setdefault("api_base", LLM_DEFAULT_API_BASE)
    config.setdefault("max_retries", LLM_MAX_RETRIES)
    config.setdefault("timeout", LLM_DEFAULT_TIMEOUT)
    config.setdefault("retryable_statuses", sorted(LLM_RETRYABLE_STATUSES))
    config.setdefault("cost_per_1k_input", None)
    config.setdefault("cost_per_1k_output", None)

    return config
