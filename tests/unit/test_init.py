"""Tests for project initialization."""
import pytest
from pathlib import Path
from datamind.config import resolve_dot_datamind, resolve_component_paths, initialize_project
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
        "graph_db", "checkpoints_db", "context_dir", "config_file",
        "data_dir", "raw_data", "processed_data",
        "scripts_dir", "describe_dir", "executions_dir",
        "skills_dir", "prompts_dir",
        "decisions_file", "exploration_file",
        "params_file", "discoveries_file",
    }
    assert set(paths.keys()) == expected_keys


def test_initialize_project_creates_all_dirs(tmp_project):
    paths = initialize_project(tmp_project)
    assert paths["graph_db"].parent.exists()  # .datamind/
    assert paths["context_dir"].exists()
    assert paths["raw_data"].exists()
    assert paths["processed_data"].exists()
    assert paths["scripts_dir"].exists()
    assert paths["describe_dir"].exists()
    assert paths["executions_dir"].exists()
    assert paths["skills_dir"].exists()


def test_initialize_project_writes_config(tmp_project):
    config = {"project_name": "test", "version": "1.0"}
    paths = initialize_project(tmp_project, config)
    import yaml
    with open(paths["config_file"]) as f:
        written = yaml.safe_load(f)
    assert written == config


def test_initialize_project_raises_for_nonexistent(tmp_project):
    bad_path = tmp_project / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        initialize_project(bad_path)
