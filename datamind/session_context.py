"""Session context propagation via Python contextvars.

Allows session_id to be read by log formatters, tool tracers, and
debug endpoints without modifying function signatures across the
call stack.

Usage:
    from datamind.session_context import _current_session_id

    # Set (typically in FastAPI middleware):
    _current_session_id.set("abc123")

    # Read (anywhere in the same async task):
    sid = _current_session_id.get()
"""

from contextvars import ContextVar

_current_session_id: ContextVar[str] = ContextVar("session_id", default="")
