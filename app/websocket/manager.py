"""
WebSocket connection manager for real-time updates.
"""
from typing import Dict, Set, Optional
from fastapi import WebSocket
import logging
import json

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        # {job_id: set of WebSocket connections}
        self.job_connections: Dict[str, Set[WebSocket]] = {}
        # {user_id: set of WebSocket connections}
        self.user_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
        """Accept new WebSocket connection."""
        await websocket.accept()

        if job_id:
            self.job_connections.setdefault(job_id, set()).add(websocket)
            logger.info("WebSocket connected to job %s", job_id)

        if user_id:
            self.user_connections.setdefault(user_id, set()).add(websocket)
            logger.info("WebSocket connected for user %s", user_id)

    def disconnect(self, websocket: WebSocket, job_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
        """Remove WebSocket connection."""
        if job_id and job_id in self.job_connections:
            self.job_connections[job_id].discard(websocket)
            if not self.job_connections[job_id]:
                del self.job_connections[job_id]

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def broadcast_job_update(self, job_id: str, data: dict) -> None:
        """Send update to all connections watching this job."""
        if job_id not in self.job_connections:
            return

        message = json.dumps({
            "type": "job_update",
            "job_id": job_id,
            "data": data,
        })

        disconnected = set()
        for connection in self.job_connections[job_id]:
            try:
                await connection.send_text(message)
            except Exception as exc:
                logger.warning("Failed to send job update: %s", exc)
                disconnected.add(connection)

        for conn in disconnected:
            self.job_connections[job_id].discard(conn)

    async def broadcast_to_user(self, user_id: str, data: dict) -> None:
        """Send update to all user's connections."""
        if user_id not in self.user_connections:
            return

        message = json.dumps({
            "type": "user_notification",
            "user_id": user_id,
            "data": data,
        })

        disconnected = set()
        for connection in self.user_connections[user_id]:
            try:
                await connection.send_text(message)
            except Exception as exc:
                logger.warning("Failed to send user update: %s", exc)
                disconnected.add(connection)

        for conn in disconnected:
            self.user_connections[user_id].discard(conn)


manager = ConnectionManager()
