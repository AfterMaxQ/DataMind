# datamind/logging_setup.py
"""JSON Lines structured logging for DataMind Studio.

Provides :class:JsonFormatter for file-based JSON output and
:func:setup_logging to configure the root logger at startup.

Stdout retains human-readable text; file output is JSON Lines.
"""

import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from datamind.session_context import _current_session_id

_BUILD_EPOCH = time.time()


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects (JSON Lines).

    Each line contains: `ts`, `level`, `module`, `event`,
    `session_id`, `data`, `elapsed_ms`.
    """

    def format(self, record: logging.LogRecord) -> str:
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        data = getattr(record, "data", {})
        if not isinstance(data, dict):
            data = {"value": str(data)}

        # Attach exception info if present
        if record.exc_info and record.exc_info[0]:
            import traceback
            tb_lines = traceback.format_exception(*record.exc_info)
            data["traceback"] = "".join(tb_lines).strip()

        payload = {
            "ts": ts,
            "level": record.levelname,
            "module": record.name,
            "event": record.getMessage(),
            "session_id": _current_session_id.get(),
            "data": data,
            "elapsed_ms": int((record.created - _BUILD_EPOCH) * 1000),
        }

        # Allow overriding fields via extra
        extra = getattr(record, "json_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    log_dir: str | None = None,
    level: str | None = None,
) -> None:
    """Configure root logger with dual output.

    - `stdout`: human-readable `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
    - `file`: JSON Lines via :class:JsonFormatter, written to
      `<log_dir>/app.jsonl` with daily rotation and 7-day retention.

    Args:
        log_dir: Path to the log directory. Defaults to
            `.datamind/logs/` relative to the project root.
        level: Log level string (DEBUG/INFO/WARNING/ERROR). Defaults to
            `DATAMIND_LOG_LEVEL` env var or `"INFO"`.
    """
    if level is None:
        level = os.environ.get("DATAMIND_LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    # Clear existing handlers to avoid duplicates on reload
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    # -- Stdout: human-readable --
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    stdout_handler.setFormatter(stdout_fmt)
    root.addHandler(stdout_handler)

    # -- File: JSON Lines --
    if log_dir is None:
        log_dir = str(Path(__file__).resolve().parent.parent / ".datamind" / "logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.jsonl"),
        when="D",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    root.info("DataMind logging initialized (level=%s, dir=%s)", level, log_dir)
