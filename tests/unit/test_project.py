"""Tests for the Project facade."""
import pytest
from pathlib import Path
from datamind.engine.project import Project
from datamind.config import initialize_project


def test_project_composes_all_services(tmp_project):
    initialize_project(tmp_project, {"project_name": "test"})
    proj = Project(str(tmp_project))
    assert proj.lineage is not None
    assert proj.cognition is not None
    assert proj.assembly is not None
    assert proj.skills is not None
    assert proj.graph is not None


def test_project_init_requires_dot_datamind(tmp_project):
    with pytest.raises(FileNotFoundError):
        Project(str(tmp_project))


def test_project_scan_raw_data(tmp_project):
    initialize_project(tmp_project)
    raw = tmp_project / "data" / "raw"
    (raw / "sample.csv").write_text("x,y\n1,2\n3,4\n")
    proj = Project(str(tmp_project))
    datasets = proj.scan_raw_data()
    assert len(datasets) == 1
    assert datasets[0]["name"] == "sample.csv"


def test_project_prompt_manager_uses_project_root(tmp_project):
    """TemplateManager should use prompts_dir from project root, not CWD."""
    initialize_project(tmp_project)
    # Create prompts directory at project root level
    prompts_dir = tmp_project / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "data-scientist.md").write_text("# Test prompt\nHello {{ context }}")
    proj = Project(str(tmp_project))
    # The TemplateManager should be able to render from the project's prompts dir
    rendered = proj.prompt_manager.render("data-scientist", {"context": "test"})
    assert "Test prompt" in rendered
    assert "Hello test" in rendered


def test_project_paths_includes_prompts_dir(tmp_project):
    """resolve_component_paths should include prompts_dir pointing to project root."""
    initialize_project(tmp_project)
    from datamind.config import resolve_component_paths
    paths = resolve_component_paths(str(tmp_project))
    assert "prompts_dir" in paths
    assert str(paths["prompts_dir"]).endswith("prompts")


def test_project_create_agent_returns_datamind_agent(tmp_project):
    """create_agent() returns a DataMindAgent wired with Project services."""
    from datamind.engine.agent import DataMindAgent
    from datamind.engine.tools import ToolRegistry
    initialize_project(tmp_project)
    proj = Project(str(tmp_project))
    agent = proj.create_agent()
    assert isinstance(agent, DataMindAgent)
    assert agent.llm_client is proj.llm_client
    assert agent.prompt_manager is proj.prompt_manager
    assert agent.usage_tracker is proj.usage_tracker
    assert agent.lineage_service is proj.lineage
    assert agent.cognition_service is proj.cognition
    assert agent.assembly_service is proj.assembly
    # v3: tool_registry is wired via create_agent()
    assert isinstance(agent._tool_registry, ToolRegistry)
    assert len(agent._tool_registry.get_definitions()) == 7
