"""Tests for AssemblyService."""
from pathlib import Path
from datamind.engine.assembly import AssemblyService, pack_manifest, estimate_tokens


def test_generate_project_md(tmp_project):
    context_dir = tmp_project / ".datamind" / "context"
    context_dir.mkdir(parents=True)
    svc = AssemblyService(None, None, str(context_dir))
    svc.generate_project_md(project_name="test-proj", datasets=["sales.csv", "users.csv"])
    project_md = context_dir / "PROJECT.md"
    assert project_md.exists()
    content = project_md.read_text()
    assert "# Project: test-proj" in content
    assert "sales.csv" in content
    assert "users.csv" in content


def test_generate_datasets_md(tmp_project):
    context_dir = tmp_project / ".datamind" / "context"
    context_dir.mkdir(parents=True)
    svc = AssemblyService(None, None, str(context_dir))
    datasets_info = [
        {"name": "sales.csv", "rows": 1000, "columns": 5, "describe_path": "describe/sales.csv.describe.md"},
        {"name": "users.csv", "rows": 500, "columns": 8, "describe_path": "describe/users.csv.describe.md"},
    ]
    svc.generate_datasets_md(datasets_info)
    datasets_md = context_dir / "DATASETS.md"
    assert datasets_md.exists()
    content = datasets_md.read_text()
    assert "sales.csv" in content
    assert "users.csv" in content
    assert "1000" in content


def test_pack_manifest_priority_order():
    result = pack_manifest(
        context_dir="/tmp/dummy",
        project_md_content="# Project",
        datasets_md_content="# Datasets",
        history_md_content="# History" * 100,
        exploration_md_content="# Exploration",
        params_md_content="# Params",
        checkpoint_md_content="# Checkpoint",
    )
    assert result.index("# Project") < result.index("# History")
    assert result.index("# History") < result.index("# Checkpoint")


def test_pack_manifest_truncates_when_over_budget():
    section = "# A section " + "word " * 5000
    result = pack_manifest(
        context_dir="/tmp/dummy",
        project_md_content="# P1 short",
        datasets_md_content="# P1 also short",
        history_md_content=section,
        exploration_md_content=section,
        params_md_content=section,
        checkpoint_md_content="# P4 checkpoint",
    )
    assert len(result) < 50000


def test_estimate_tokens():
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("") == 0
    text = "a " * 400
    tokens = estimate_tokens(text)
    assert 80 <= tokens <= 120
