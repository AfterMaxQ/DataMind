"""Tests for the EventSourcing layer."""
import json
from pathlib import Path
from datamind.engine.events import ExecutionLog


def test_write_execution_log(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    log_id = el.record(
        script_path="scripts/clean.py",
        status="success",
        inputs=["data/raw/sales.csv"],
        outputs=["data/processed/clean_sales.csv"],
        stdout="Cleaning complete",
        stderr="",
        exit_code=0,
        params={"fill_method": "forward"},
    )
    assert log_id is not None
    log_path = exec_dir / f"{log_id}.json"
    assert log_path.exists()
    content = json.loads(log_path.read_text())
    assert content["script_path"] == "scripts/clean.py"
    assert content["status"] == "success"
    assert content["exit_code"] == 0


def test_record_failure(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    log_id = el.record(
        script_path="scripts/broken.py",
        status="failure",
        inputs=["data/raw/sales.csv"],
        outputs=[],
        stdout="",
        stderr="KeyError: 'col_x'",
        exit_code=1,
        params={},
    )
    log_path = exec_dir / f"{log_id}.json"
    content = json.loads(log_path.read_text())
    assert content["status"] == "failure"
    assert "KeyError" in content["stderr"]


def test_list_recent(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    el.record(script_path="a.py", status="success")
    el.record(script_path="b.py", status="failure")
    el.record(script_path="c.py", status="success")

    recent = el.list_recent(limit=2)
    assert len(recent) == 2
    assert recent[0]["script_path"] == "c.py"  # most recent first
    assert recent[1]["script_path"] == "b.py"


def test_count_since(tmp_project):
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()
    el = ExecutionLog(str(exec_dir))
    for i in range(5):
        el.record(script_path=f"s{i}.py", status="success")
    assert el.count_since("1970-01-01T00:00:00Z") == 5
