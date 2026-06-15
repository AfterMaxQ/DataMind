"""CognitionService — decisions, exploration tree, params, discoveries (Layer 2)."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class CognitionService:
    """Logs and queries cognitive journey data."""

    def __init__(self, decisions_file: str, exploration_file: str, params_file: str, discoveries_file: str):
        self.decisions_file = Path(decisions_file)
        self.exploration_file = Path(exploration_file)
        self.params_file = Path(params_file)
        self.discoveries_file = Path(discoveries_file)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def log_decision(self, what: str, why: str, alternatives: list[str] | None = None, implications: str = "") -> str:
        d_id = self._new_id()
        entry = {"id": d_id, "what": what, "why": why, "alternatives": alternatives or [], "implications": implications, "timestamp": self._now()}
        self._append_jsonl(self.decisions_file, entry)
        return d_id

    def get_recent_decisions(self, limit: int = 5) -> list[dict]:
        return self._read_jsonl_reverse(self.decisions_file, limit)

    def add_exploration_node(self, description: str, status: str, parent_id: str | None = None, reason: str = "") -> str:
        node_id = self._new_id()
        node = {"id": node_id, "description": description, "status": status, "reason": reason, "parent_id": parent_id, "children": [], "timestamp": self._now()}
        tree = self._read_json(self.exploration_file, [])
        tree.append(node)
        if parent_id:
            parent = next((n for n in tree if n["id"] == parent_id), None)
            if parent:
                parent.setdefault("children", []).append(node_id)
        self._write_json(self.exploration_file, tree)
        return node_id

    def get_exploration_tree(self) -> list[dict]:
        return self._read_json(self.exploration_file, [])

    def add_discovery(self, finding: str, tag: str = "", linked_code: str = "", linked_data: str = "") -> str:
        d_id = self._new_id()
        entry = {"id": d_id, "finding": finding, "tag": tag, "linked_code": linked_code, "linked_data": linked_data, "timestamp": self._now()}
        self._append_jsonl(self.discoveries_file, entry)
        return d_id

    def get_recent_discoveries(self, limit: int = 5) -> list[dict]:
        return self._read_jsonl_reverse(self.discoveries_file, limit)

    def register_params(self, script_id: str, run_id: str, params: dict) -> None:
        all_params = self._read_json(self.params_file, {})
        all_params.setdefault(script_id, {})[run_id] = {"params": params, "timestamp": self._now()}
        self._write_json(self.params_file, all_params)

    def get_params(self, script_id: str) -> dict[str, dict]:
        return self._read_json(self.params_file, {}).get(script_id, {})

    def _append_jsonl(self, path: Path, entry: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _read_jsonl_reverse(self, path: Path, limit: int) -> list[dict]:
        if not path.exists():
            return []
        entries = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        result = entries[-limit:] if len(entries) > limit else entries
        return list(reversed(result))

    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
