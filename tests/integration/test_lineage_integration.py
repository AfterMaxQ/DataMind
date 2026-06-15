"""Integration tests for LineageService with real files."""
import pandas as pd
from datamind.engine.graph import GraphDB
from datamind.engine.describe import DescribeEngine
from datamind.engine.events import ExecutionLog
from datamind.engine.lineage import LineageService


def test_full_lineage_workflow(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    describe_dir = tmp_project / "describe"
    exec_dir = tmp_project / "executions"
    scripts_dir = tmp_project / "scripts"
    processed_dir = tmp_project / "data" / "processed"
    for d in [raw_dir, describe_dir, exec_dir, scripts_dir, processed_dir]:
        d.mkdir(parents=True)

    df = pd.DataFrame({"price": [10, 20, 30, None, 50]})
    df.to_csv(raw_dir / "sales.csv", index=False)

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(exec_dir))
    describe = DescribeEngine(str(describe_dir))
    svc = LineageService(graph, describe, exec_log)

    datasets = svc.scan_raw_data(str(tmp_project))
    assert len(datasets) == 1
    assert datasets[0]["name"] == "sales.csv"

    describe_files = list(describe_dir.glob("*.md"))
    assert len(describe_files) == 1

    processed_csv = processed_dir / "sales_clean.csv"
    pd.DataFrame({"price": [10.0, 20.0, 30.0, 30.0, 50.0]}).to_csv(processed_csv, index=False)

    result = svc.link_script_to_datasets(
        script_path="scripts/clean_sales.py",
        input_paths=[str(raw_dir / "sales.csv")],
        output_paths=[str(processed_csv)],
    )

    exec_log.record(
        script_path="scripts/clean_sales.py", status="success",
        inputs=[str(raw_dir / "sales.csv")], outputs=[str(processed_csv)], exit_code=0,
    )

    ancestors = svc.query_ancestors(datasets[0]["id"])
    assert datasets[0]["id"] is not None
    graph.close()
