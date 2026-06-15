"""Event sourcing — immutable execution logs."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class ExecutionLog:
    """Append-only execution log writer and reader."""

    def __init__(self, executions_dir: str):
        self.dir = Path(executions_dir)
        self._counter = 0

    def _now(self) -> str:
        self._counter += 1
        ts = datetime.now(timezone.utc).isoformat()
        return f"{ts}#{self._counter:06d}"

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def record(
        self,
        script_path: str,
        status: str,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        params: dict | None = None,
    ) -> str:
        """Record an execution event. Returns the log ID."""
        log_id = self._new_id()
        entry = {
            "id": log_id,
            "script_path": script_path,
            "status": status,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "params": params or {},
            "timestamp": self._now(),
        }
        log_path = self.dir / f"{log_id}.json"
        log_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False))
        return log_id

    def read(self, log_id: str) -> dict | None:
        """Read a single execution log by ID."""
        log_path = self.dir / f"{log_id}.json"
        if not log_path.exists():
            return None
        return json.loads(log_path.read_text())

    def list_recent(self, limit: int = 10) -> list[dict]:
        """List recent execution logs, newest first."""
        logs = []
        for f in self.dir.glob("*.json"):
            logs.append(json.loads(f.read_text()))
        logs.sort(key=lambda e: e["timestamp"], reverse=True)
        return logs[:limit]

    def count_since(self, since_timestamp: str) -> int:
        """Count execution logs with timestamp >= since_timestamp."""
        count = 0
        for f in self.dir.glob("*.json"):
            entry = json.loads(f.read_text())
            if entry["timestamp"] >= since_timestamp:
                count += 1
        return count
