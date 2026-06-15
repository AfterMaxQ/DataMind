"""Tests for CognitionService."""
import json
from datamind.engine.cognition import CognitionService


def test_log_decision_appends_to_jsonl(tmp_project):
    decisions_file = tmp_project / "decisions.jsonl"
    svc = CognitionService(
        decisions_file=str(decisions_file),
        exploration_file=str(tmp_project / "exploration.json"),
        params_file=str(tmp_project / "params.json"),
        discoveries_file=str(tmp_project / "discoveries.jsonl"),
    )
    d_id = svc.log_decision(
        what="forward fill", why="stocks don't interpolate on weekends",
        alternatives=["interpolation", "drop"], implications="preserves weekend gap structure",
    )
    assert decisions_file.exists()
    lines = decisions_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["what"] == "forward fill"
    assert entry["id"] == d_id


def test_get_recent_decisions(tmp_project):
    decisions_file = tmp_project / "decisions.jsonl"
    svc = CognitionService(
        decisions_file=str(decisions_file),
        exploration_file=str(tmp_project / "exploration.json"),
        params_file=str(tmp_project / "params.json"),
        discoveries_file=str(tmp_project / "discoveries.jsonl"),
    )
    for i in range(5):
        svc.log_decision(what=f"decision {i}", why="testing")
    recent = svc.get_recent_decisions(limit=3)
    assert len(recent) == 3
    assert recent[0]["what"] == "decision 4"


def test_add_exploration_node_and_tree(tmp_project):
    exploration_file = tmp_project / "exploration.json"
    svc = CognitionService(
        decisions_file=str(tmp_project / "decisions.jsonl"),
        exploration_file=str(exploration_file),
        params_file=str(tmp_project / "params.json"),
        discoveries_file=str(tmp_project / "discoveries.jsonl"),
    )
    root_id = svc.add_exploration_node(description="Try XGBoost", status="SELECTED")
    child_id = svc.add_exploration_node(description="Tune learning rate", status="EXPLORATORY", parent_id=root_id)
    tree = svc.get_exploration_tree()
    assert len(tree) == 2
    root = next(n for n in tree if n["id"] == root_id)
    assert child_id in root["children"]


def test_add_discovery(tmp_project):
    discoveries_file = tmp_project / "discoveries.jsonl"
    svc = CognitionService(
        decisions_file=str(tmp_project / "decisions.jsonl"),
        exploration_file=str(tmp_project / "exploration.json"),
        params_file=str(tmp_project / "params.json"),
        discoveries_file=str(discoveries_file),
    )
    d_id = svc.add_discovery(finding="Price shows weekly seasonality", tag="pattern", linked_data="data/raw/sales.csv")
    discoveries = svc.get_recent_discoveries(5)
    assert len(discoveries) == 1
    assert "seasonality" in discoveries[0]["finding"]
