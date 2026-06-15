"""Tests for the GraphDB layer."""
import json
import sqlite3
from datamind.engine.graph import GraphDB


def test_graphdb_init_creates_tables(tmp_project):
    db_path = tmp_project / "test.db"
    db = GraphDB(str(db_path))
    db.initialize()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    db.close()

    assert "nodes" in tables
    assert "edges" in tables


def test_graphdb_init_sets_wal_mode(tmp_project):
    db_path = tmp_project / "test.db"
    db = GraphDB(str(db_path))
    db.initialize()

    conn = sqlite3.connect(str(db_path))
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    db.close()

    assert journal_mode.lower() == "wal"


def test_graphdb_init_idempotent(tmp_project):
    db_path = tmp_project / "test.db"
    db1 = GraphDB(str(db_path))
    db1.initialize()
    db1.close()

    db2 = GraphDB(str(db_path))
    db2.initialize()  # should not raise
    db2.close()


def test_insert_node_and_get(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    node_id = db.insert_node(
        type="dataset",
        name="sales.csv",
        path="data/raw/sales.csv",
        metadata={"rows": 100, "columns": 5},
    )
    node = db.get_node(node_id)
    assert node["type"] == "dataset"
    assert node["name"] == "sales.csv"
    assert json.loads(node["metadata"]) == {"rows": 100, "columns": 5}
    db.close()


def test_insert_edge_links_nodes(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    src = db.insert_node(type="script", name="clean.py")
    tgt = db.insert_node(type="dataset", name="clean_sales.csv")
    edge_id = db.insert_edge(
        source_id=src,
        target_id=tgt,
        edge_type="PRODUCED",
        metadata={"row_count": 100},
    )
    edge = db.get_edge(edge_id)
    assert edge["source_id"] == src
    assert edge["target_id"] == tgt
    assert edge["edge_type"] == "PRODUCED"
    db.close()


def test_query_ancestors(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    raw = db.insert_node(type="dataset", name="raw.csv")
    script = db.insert_node(type="script", name="process.py")
    processed = db.insert_node(type="dataset", name="processed.csv")
    db.insert_edge(source_id=script, target_id=processed, edge_type="PRODUCED")
    db.insert_edge(source_id=raw, target_id=script, edge_type="USED_INPUT")

    ancestors = db.query_ancestors(processed)
    ancestor_ids = [n["id"] for n in ancestors]
    assert raw in ancestor_ids
    assert script in ancestor_ids
    assert processed not in ancestor_ids
    db.close()


def test_query_descendants(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    raw = db.insert_node(type="dataset", name="raw.csv")
    script = db.insert_node(type="script", name="process.py")
    processed = db.insert_node(type="dataset", name="processed.csv")
    model = db.insert_node(type="finding", name="model_results")
    db.insert_edge(source_id=raw, target_id=script, edge_type="USED_INPUT")
    db.insert_edge(source_id=script, target_id=processed, edge_type="PRODUCED")
    db.insert_edge(source_id=processed, target_id=model, edge_type="TRIGGERED")

    descendants = db.query_descendants(raw)
    descendant_ids = [n["id"] for n in descendants]
    assert script in descendant_ids
    assert processed in descendant_ids
    assert model in descendant_ids
    assert raw not in descendant_ids
    db.close()


def test_list_nodes_by_type(tmp_project):
    db = GraphDB(str(tmp_project / "test.db"))
    db.initialize()
    db.insert_node(type="dataset", name="a.csv")
    db.insert_node(type="dataset", name="b.csv")
    db.insert_node(type="script", name="s.py")

    datasets = db.list_nodes_by_type("dataset")
    assert len(datasets) == 2
    scripts = db.list_nodes_by_type("script")
    assert len(scripts) == 1
    db.close()
