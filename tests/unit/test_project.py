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
