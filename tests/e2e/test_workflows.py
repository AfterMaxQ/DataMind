"""End-to-end workflow tests."""
from datamind.engine.project import Project


def test_full_data_cleaning_workflow(e2e_project):
    proj = Project(str(e2e_project))
    datasets = proj.scan_raw_data()
    assert len(datasets) >= 1
    sales = [d for d in datasets if d["name"] == "sales.csv"][0]
    describe_dir = e2e_project / "describe"
    describe_files = list(describe_dir.glob("*.md"))
    assert len(describe_files) >= 1
    desc_content = describe_files[0].read_text()
    assert "sales.csv" in desc_content
    assert "price" in desc_content
    d_id = proj.cognition.log_decision(what="remove outliers", why="prices outside 3-sigma", alternatives=["winsorize"])
    assert d_id is not None
    decisions = proj.cognition.get_recent_decisions(5)
    assert len(decisions) >= 1
    exec_id = proj.exec_log.record(script_path="scripts/clean.py", status="success", exit_code=0)
    assert exec_id is not None
    recent = proj.exec_log.list_recent(5)
    assert len(recent) >= 1


def test_cognitive_journey_workflow(e2e_project):
    proj = Project(str(e2e_project))
    root_id = proj.cognition.add_exploration_node(description="Analyze price trends", status="SELECTED")
    child_id = proj.cognition.add_exploration_node(description="Try seasonal decomposition", status="EXPLORATORY", parent_id=root_id)
    tree = proj.cognition.get_exploration_tree()
    assert len(tree) == 2
    proj.cognition.add_discovery(finding="Price shows weekly seasonality", tag="pattern")
    discoveries = proj.cognition.get_recent_discoveries(5)
    assert len(discoveries) >= 1


def test_context_assembly_workflow(e2e_project):
    proj = Project(str(e2e_project))
    proj.lineage.scan_raw_data(str(e2e_project))
    proj.cognition.log_decision(what="test", why="testing")
    proj.cognition.add_discovery(finding="test finding", tag="test")
    generated = proj.assembly.refresh_all(project_name="E2E Test", dataset_names=["sales.csv"], datasets_info=[{"name": "sales.csv", "rows": 100, "columns": 3}])
    context_dir = e2e_project / ".datamind" / "context"
    assert (context_dir / "PROJECT.md").exists()
    assert (context_dir / "DATASETS.md").exists()
    assert (context_dir / "HISTORY.md").exists()
    history = (context_dir / "HISTORY.md").read_text()
    assert "test" in history
