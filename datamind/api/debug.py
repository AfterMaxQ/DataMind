# datamind/api/debug.py
"""Debug and introspection endpoints for DataMind Studio.

Mounted conditionally -- gated by the `DATAMIND_DEBUG_DISABLE`
environment variable.  Provides runtime visibility into active
sessions, agent state, and structured logs.

Endpoints:
    GET /debug/state/{session_id}   -- Full runtime state of a session
    GET /debug/sessions             -- Summary of all active sessions
    GET /debug/logs                 -- Query structured log entries
"""

import json
import logging
import os
from fastapi import APIRouter, HTTPException, Query, Request

_log = logging.getLogger(__name__)
debug_router = APIRouter(prefix="/debug", tags=["debug"])


@debug_router.get("/state/{session_id}")
async def get_state(session_id: str, request: Request):
    """Return full runtime state for a session.

    Response keys: session_id, skill_name, current_phase, phases,
    result, agent_type, started_at, updated_at.
    """
    registry = getattr(request.app.state, "session_registry", {})
    entry = registry.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    sm = entry.get("state_machine")
    agent = entry.get("agent")

    return {
        "session_id": session_id,
        "skill_name": sm.state.skill if sm else entry.get("skill_name", ""),
        "current_phase": sm.state.phase if sm else "",
        "started_at": entry.get("started_at", ""),
        "updated_at": entry.get("updated_at", ""),
        "phases": sm.state.phases if sm else {},
        "result": sm.state.result if sm else None,
        "agent_type": type(agent).__name__ if agent else "unknown",
    }


@debug_router.get("/sessions")
async def list_sessions(request: Request):
    """Return summary list of all active sessions.

    Each entry: session_id, skill_name, phase, started_at.
    """
    registry = getattr(request.app.state, "session_registry", {})
    sessions = []
    for sid, entry in registry.items():
        sm = entry.get("state_machine")
        sessions.append({
            "session_id": sid,
            "skill_name": sm.state.skill if sm else entry.get("skill_name", ""),
            "phase": sm.state.phase if sm else "",
            "started_at": entry.get("started_at", ""),
        })
    return {"sessions": sessions}


@debug_router.get("/logs")
async def query_logs(
    request: Request,
    session_id: str | None = Query(None, description="Filter by session_id"),
    level: str | None = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
):
    """Query structured log entries from the JSONL log file.

    Supports optional filtering by session_id and log level.
    """
    log_dir = os.path.join(os.getcwd(), ".datamind", "logs")
    log_file = os.path.join(log_dir, "app.jsonl")

    entries: list[dict] = []

    if os.path.isfile(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if session_id and rec.get("session_id") != session_id:
                    continue
                if level and rec.get("level", "").upper() != level.upper():
                    continue

                entries.append(rec)
                if len(entries) >= limit:
                    break

    return {
        "session_id": session_id,
        "level": level,
        "limit": limit,
        "count": len(entries),
        "logs": entries,
    }
