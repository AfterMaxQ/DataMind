"""Tests for tool call tracing in ToolRegistry.execute()."""

import json
import logging
import io
from datamind.engine.tools import ToolRegistry
from datamind.logging_setup import JsonFormatter
from datamind.session_context import _current_session_id


def _make_registry() -> ToolRegistry:
    """Create a minimal ToolRegistry with a single echo tool."""
    reg = ToolRegistry()
    def echo(**kwargs) -> dict:
        return {"echoed": kwargs}
    reg.register("echo", {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo back arguments",
            "parameters": {"type": "object", "properties": {}},
        },
    }, echo)
    return reg


def test_tool_execute_logs_success_event():
    """A successful tool call emits a 'tool_call' log event."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)

    _current_session_id.set("trace-test-1")
    reg = _make_registry()
    result = reg.execute("echo", {"x": 42})

    assert result == {"echoed": {"x": 42}}

    root.removeHandler(handler)
    handler.flush()
    output = stream.getvalue().strip()
    lines = [l for l in output.split("\n") if l]
    tool_events = [json.loads(l) for l in lines
                   if json.loads(l).get("event") == "tool_call"]

    assert len(tool_events) == 1, f"Expected 1 tool_call event, got {len(tool_events)}"
    ev = tool_events[0]
    assert ev["session_id"] == "trace-test-1"
    assert ev["data"]["tool"] == "echo"
    assert ev["data"]["status"] == "success"
    assert ev["data"]["elapsed_ms"] >= 0


def test_tool_execute_logs_error_event():
    """A failed tool call emits a 'tool_call' event with status='error'."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)

    _current_session_id.set("trace-test-2")
    reg = _make_registry()

    try:
        reg.execute("echo", None)
    except TypeError:
        pass

    root.removeHandler(handler)
    handler.flush()
    output = stream.getvalue().strip()
    error_events = [json.loads(l) for l in output.split("\n") if l
                    and json.loads(l).get("event") == "tool_call"
                    and json.loads(l).get("data", {}).get("status") == "error"]

    assert len(error_events) >= 1, f"Expected >=1 tool_call error, got {len(error_events)}"


def test_unknown_tool_raises_value_error():
    """Calling an unregistered tool raises ValueError."""
    import pytest
    reg = _make_registry()
    with pytest.raises(ValueError, match="Unknown tool"):
        reg.execute("nonexistent", {})
