"""Tests for project initialization."""
from pathlib import Path
from datamind.config import resolve_dot_datamind, resolve_component_paths
from datamind import __version__


def test_version():
    assert __version__ == "0.1.0"


def test_resolve_dot_datamind():
    result = resolve_dot_datamind("/home/user/myproject")
    expected = Path("/home/user/myproject").resolve() / ".datamind"
    assert result == expected


def test_resolve_component_paths_returns_all_keys():
    paths = resolve_component_paths("/tmp/test_project")
    expected_keys = {
        "graph_db", "context_dir", "config_file",
        "data_dir", "raw_data", "processed_data",
        "scripts_dir", "describe_dir", "executions_dir",
        "skills_dir", "decisions_file", "exploration_file",
        "params_file", "discoveries_file",
    }
    assert set(paths.keys()) == expected_keys
