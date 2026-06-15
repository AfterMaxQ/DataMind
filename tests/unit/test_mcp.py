"""Tests for MCP Server tools."""
from datamind.config import initialize_project
from datamind.engine.project import Project
from datamind.mcp.server import (
    tool_read_context, tool_register_dataset,
    tool_log_decision, tool_list_datasets,
)


def test_tool_read_context(tmp_project):
    initialize_project(tmp_project)
    proj = Project(str(tmp_project))
    result = tool_read_context(proj)
    assert isinstance(result, str)
    assert "Context" in result


def test_tool_register_dataset(tmp_project):
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "test.csv").write_text("x\n1\n")
    proj = Project(str(tmp_project))
    result = tool_register_dataset(proj, str(raw / "test.csv"))
    assert "test.csv" in result


def test_tool_log_decision(tmp_project):
    initialize_project(tmp_project)
    proj = Project(str(tmp_project))
    result = tool_log_decision(proj, "use forward fill", "stocks don't interpolate")
    assert result["what"] == "use forward fill"


def test_tool_list_datasets(tmp_project):
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "a.csv").write_text("x\n1\n")
    proj = Project(str(tmp_project))
    proj.lineage.register_dataset(str(raw / "a.csv"))
    result = tool_list_datasets(proj)
    assert len(result) >= 1
