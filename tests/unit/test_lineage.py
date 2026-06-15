"""Tests for LineageService."""
from datamind.engine.lineage import LineageService
from datamind.engine.graph import GraphDB
from datamind.engine.events import ExecutionLog
from datamind.engine.describe import DescribeEngine


def test_register_dataset_creates_node(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    csv_path = raw_dir / "test.csv"
    csv_path.write_text("a,b\n1,2\n")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(tmp_project / "executions"))
    describe = DescribeEngine(str(describe_dir))
    svc = LineageService(graph, describe, exec_log)

    node_id = svc.register_dataset(str(csv_path))
    node = graph.get_node(node_id)
    assert node is not None
    assert node["type"] == "dataset"
    assert node["name"] == "test.csv"
    assert node["path"] == str(csv_path)
    graph.close()


def test_find_dataset_by_path(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "a.csv").write_text("x,y\n1,2\n")
    (raw_dir / "b.csv").write_text("x,y\n3,4\n")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(tmp_project / "executions"))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    svc.register_dataset(str(raw_dir / "a.csv"))
    svc.register_dataset(str(raw_dir / "b.csv"))

    node = svc.find_dataset_by_path(str(raw_dir / "a.csv"))
    assert node is not None
    assert node["name"] == "a.csv"
    assert svc.find_dataset_by_path("/nonexistent.csv") is None
    graph.close()


def test_scan_raw_data_detects_all(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "a.csv").write_text("x\n1\n")
    (raw_dir / "b.csv").write_text("x\n2\n")
    (raw_dir / "notes.txt").write_text("hello")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(exec_dir))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    datasets = svc.scan_raw_data(str(tmp_project))
    names = [d["name"] for d in datasets]
    assert "a.csv" in names
    assert "b.csv" in names
    assert "notes.txt" not in names
    graph.close()


def test_link_script_to_datasets(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "in.csv").write_text("x\n1\n")
    processed_dir = tmp_project / "data" / "processed"
    processed_dir.mkdir(parents=True)
    (processed_dir / "out.csv").write_text("x\n1\n")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(exec_dir))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    svc.register_dataset(str(raw_dir / "in.csv"))
    svc.register_dataset(str(processed_dir / "out.csv"))

    result = svc.link_script_to_datasets(
        script_path="scripts/process.py",
        input_paths=[str(raw_dir / "in.csv")],
        output_paths=[str(processed_dir / "out.csv")],
    )
    assert result["script_node_id"] is not None
    assert len(result["edges"]["inputs"]) == 1
    assert len(result["edges"]["outputs"]) == 1
    graph.close()


def test_reproduce_returns_script_chain(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "raw.csv").write_text("a,b\n1,2\n")
    processed_dir = tmp_project / "data" / "processed"
    processed_dir.mkdir(parents=True)
    (processed_dir / "clean.csv").write_text("a,b\n1,2\n")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(exec_dir))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    svc.register_dataset(str(raw_dir / "raw.csv"))
    svc.register_dataset(str(processed_dir / "clean.csv"))

    svc.link_script_to_datasets(
        script_path="scripts/clean.py",
        input_paths=[str(raw_dir / "raw.csv")],
        output_paths=[str(processed_dir / "clean.csv")],
    )

    scripts = svc.reproduce(str(processed_dir / "clean.csv"))
    assert len(scripts) == 1
    assert scripts[0] == "scripts/clean.py"
    graph.close()


def test_reproduce_with_multi_script_chain(tmp_project):
    raw_dir = tmp_project / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "raw.csv").write_text("a,b\n1,2\n")
    processed_dir = tmp_project / "data" / "processed"
    processed_dir.mkdir(parents=True)
    (processed_dir / "clean.csv").write_text("a,b\n1,2\n")
    (processed_dir / "report.csv").write_text("summary\nok\n")
    describe_dir = tmp_project / "describe"
    describe_dir.mkdir()
    exec_dir = tmp_project / "executions"
    exec_dir.mkdir()

    graph = GraphDB(str(tmp_project / "test.db"))
    graph.initialize()
    exec_log = ExecutionLog(str(exec_dir))
    svc = LineageService(graph, DescribeEngine(str(describe_dir)), exec_log)

    svc.register_dataset(str(raw_dir / "raw.csv"))
    svc.register_dataset(str(processed_dir / "clean.csv"))
    svc.register_dataset(str(processed_dir / "report.csv"))

    svc.link_script_to_datasets(
        script_path="scripts/clean.py",
        input_paths=[str(raw_dir / "raw.csv")],
        output_paths=[str(processed_dir / "clean.csv")],
    )
    svc.link_script_to_datasets(
        script_path="scripts/analyze.py",
        input_paths=[str(processed_dir / "clean.csv")],
        output_paths=[str(processed_dir / "report.csv")],
    )

    scripts = svc.reproduce(str(processed_dir / "report.csv"))
    assert len(scripts) == 2
    # Raw-data scripts first: clean.py before analyze.py
    assert scripts[0] == "scripts/clean.py"
    assert scripts[1] == "scripts/analyze.py"
    graph.close()
