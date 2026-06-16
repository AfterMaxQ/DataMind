"""WebSocket connection manager for real-time event broadcasting.

Provides :class:`ConnectionManager` which tracks active WebSocket
connections per session and supports broadcasting typed events to
connected clients.
"""

import json
import logging
from fastapi import WebSocket

_log = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by session id.

    Tracks active connections and provides methods to broadcast
    typed JSON events to all clients in a session or globally.

    Event types defined by the client contract:
    - ``lineage_update`` — a dataset or script node was added/changed.
    - ``decision_update`` — a new decision was recorded.
    - ``phase_transition`` — a skill phase changed state.
    - ``token_stream`` — LLM tokens are arriving in real time.
    """

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str = "global") -> None:
        """Accept and register a WebSocket connection.

        Args:
            websocket: The incoming WebSocket connection.
            session_id: Session identifier for scoped broadcasts.
                Defaults to ``"global"``.
        """
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        _log.debug("WebSocket connected to session %s (total: %d)",
                    session_id, len(self.active_connections[session_id]))

    def disconnect(self, websocket: WebSocket, session_id: str = "global") -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The connection to remove.
            session_id: The session the connection was registered under.
        """
        try:
            if session_id in self.active_connections:
                self.active_connections[session_id].remove(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
        except (ValueError, KeyError):
            pass

    async def broadcast(
        self,
        event_type: str,
        data: dict,
        session_id: str | None = None,
    ) -> None:
        """Send a typed JSON event to connected clients.

        Args:
            event_type: One of ``lineage_update``, ``decision_update``,
                ``phase_transition``, or ``token_stream``.
            data: Event payload dict.
            session_id: If provided, broadcast only to this session.
                If ``None``, broadcast to all sessions.
        """
        if session_id is not None:
            targets = list(self.active_connections.get(session_id, []))
        else:
            targets = [
                ws
                for conns in self.active_connections.values()
                for ws in conns
            ]

        if not targets:
            return

        message = json.dumps({"event": event_type, "data": data})
        for websocket in targets:
            try:
                await websocket.send_text(message)
            except Exception:
                _log.debug("Failed to send to a WebSocket client", exc_info=True)

    async def broadcast_to_all(self, event_type: str, data: dict) -> None:
        """Broadcast an event to every connected client across all sessions.

        Convenience wrapper around :meth:`broadcast` with ``session_id=None``.
        """
        await self.broadcast(event_type, data, session_id=None)
