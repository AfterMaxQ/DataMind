# tests/unit/test_debug_endpoints.py
"""Tests for debug API endpoints."""

import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from datamind.api.app import create_app


def _make_test_app():
    """Create a FastAPI test app with a temp project root structure."""
    tmp = tempfile.mkdtemp(prefix="datamind_debug_test_")
    dot = Path(tmp) / ".datamind"
    dot.mkdir(parents=True)
    (dot / "config.yaml").write_text("provider: deepseek\n", encoding="utf-8")
    for d in ["data/raw", "data/processed", "scripts", "skills", "prompts",
              "describe", "executions", "context"]:
        (Path(tmp) / d).mkdir(parents=True, exist_ok=True)
    app = create_app(tmp)
    return app, tmp


def test_debug_router_mounted_when_not_disabled():
    """Debug endpoints accessible when DATAMIND_DEBUG_DISABLE is not set."""
    os.environ.pop("DATAMIND_DEBUG_DISABLE", None)
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/debug/sessions")
    assert resp.status_code == 200
    assert resp.json() == {"sessions": []}
    resp = client.get("/debug/logs")
    assert resp.status_code == 200
    assert "logs" in resp.json()


def test_debug_state_returns_404_for_unknown_session():
    """Unknown session_id returns 404."""
    os.environ.pop("DATAMIND_DEBUG_DISABLE", None)
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/debug/state/nonexistent-session")
    assert resp.status_code == 404


def test_debug_disabled_when_env_var_set():
    """All debug endpoints return 404 when DATAMIND_DEBUG_DISABLE=1."""
    os.environ["DATAMIND_DEBUG_DISABLE"] = "1"
    try:
        app, _ = _make_test_app()
        client = TestClient(app)
        for path in ["/debug/sessions", "/debug/state/any", "/debug/logs"]:
            assert client.get(path).status_code == 404
    finally:
        os.environ.pop("DATAMIND_DEBUG_DISABLE", None)


def test_debug_logs_with_query_params():
    """Debug /logs endpoint accepts query parameters."""
    os.environ.pop("DATAMIND_DEBUG_DISABLE", None)
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/debug/logs?session_id=abc&level=INFO&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "abc"
    assert data["level"] == "INFO"
    assert "logs" in data
