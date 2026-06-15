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
