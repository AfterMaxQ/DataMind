"""Tests for the GraphDB layer."""
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
