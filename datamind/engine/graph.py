"""Graph database — SQLite-backed nodes and edges store."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from datamind.config import SQLITE_PRAGMAS


class GraphDB:
    """SQLite-backed graph database for typed nodes and directed edges."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            for pragma in SQLITE_PRAGMAS:
                self._conn.execute(pragma)
        return self._conn

    def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                path TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES nodes(id),
                target_id TEXT NOT NULL REFERENCES nodes(id),
                edge_type TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
        """)
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    # -- Nodes --

    def insert_node(self, type: str, name: str, path: str | None = None, metadata: dict | None = None) -> str:
        node_id = self._new_id()
        self.conn.execute(
            "INSERT INTO nodes (id, type, name, path, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (node_id, type, name, path, json.dumps(metadata or {}), self._now()),
        )
        self.conn.commit()
        return node_id

    def get_node(self, node_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_nodes_by_type(self, type: str) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM nodes WHERE type = ? ORDER BY created_at", (type,)).fetchall()
        return [dict(r) for r in rows]

    # -- Edges --

    def insert_edge(self, source_id: str, target_id: str, edge_type: str, metadata: dict | None = None) -> str:
        edge_id = self._new_id()
        self.conn.execute(
            "INSERT INTO edges (id, source_id, target_id, edge_type, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (edge_id, source_id, target_id, edge_type, json.dumps(metadata or {}), self._now()),
        )
        self.conn.commit()
        return edge_id

    def get_edge(self, edge_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    # -- Traversal --

    def query_ancestors(self, node_id: str) -> list[dict]:
        """BFS walk from target -> source to find all upstream nodes."""
        visited = set()
        result = []
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            rows = self.conn.execute(
                "SELECT n.* FROM nodes n JOIN edges e ON n.id = e.source_id WHERE e.target_id = ?", (current,)
            ).fetchall()
            for row in rows:
                nid = row["id"]
                if nid not in visited and nid != node_id:
                    visited.add(nid)
                    result.append(dict(row))
                    queue.append(nid)
        return result

    def query_descendants(self, node_id: str) -> list[dict]:
        """BFS walk from source -> target to find all downstream nodes."""
        visited = set()
        result = []
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            rows = self.conn.execute(
                "SELECT n.* FROM nodes n JOIN edges e ON n.id = e.target_id WHERE e.source_id = ?", (current,)
            ).fetchall()
            for row in rows:
                nid = row["id"]
                if nid not in visited and nid != node_id:
                    visited.add(nid)
                    result.append(dict(row))
                    queue.append(nid)
        return result
