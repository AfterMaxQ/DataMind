"""Tests for datamind.logging_setup.JsonFormatter."""

import json
import logging
import io
from datamind.logging_setup import JsonFormatter
from datamind.session_context import _current_session_id


def test_json_formatter_emits_valid_json_lines():
    """JsonFormatter produces valid JSON with all required fields."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    fmt = JsonFormatter()
    handler.setFormatter(fmt)

    logger = logging.getLogger("test_json")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    _current_session_id.set("session-abc-123")
    logger.info("User connected", extra={"data": {"ip": "127.0.0.1"}})

    handler.flush()
    line = stream.getvalue().strip()
    assert line, "Expected at least one log line"

    record = json.loads(line)
    assert record["level"] == "INFO"
    assert record["module"] == "test_json"
    assert record["event"] == "User connected"
    assert record["session_id"] == "session-abc-123"
    assert record["data"] == {"ip": "127.0.0.1"}
    assert "ts" in record
    assert "elapsed_ms" in record


def test_json_formatter_without_session_id():
    """When no session_id is set, the field is an empty string."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_no_session")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    _current_session_id.set("")
    logger.warning("No session")
    handler.flush()

    record = json.loads(stream.getvalue().strip())
    assert record["session_id"] == ""
    assert record["level"] == "WARNING"


def test_json_formatter_error_includes_traceback():
    """Exception log records include traceback in data."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_error")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    try:
        raise ValueError("bad input")
    except ValueError:
        logger.error("Caught error", exc_info=True)

    handler.flush()
    record = json.loads(stream.getvalue().strip())
    assert record["level"] == "ERROR"
    assert "bad input" in record.get("data", {}).get("traceback", "")
