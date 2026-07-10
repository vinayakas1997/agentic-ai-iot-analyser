import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_connections: dict[str, list[WebSocket]] = {}


async def websocket_endpoint(websocket: WebSocket) -> None:
    user_id = settings.default_user_id
    await websocket.accept()
    _connections.setdefault(user_id, []).append(websocket)
    logger.info("WS connected user %s", user_id)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections[user_id].remove(websocket)
        if not _connections[user_id]:
            del _connections[user_id]


async def broadcast_event(user_id: str, message: dict[str, Any]) -> None:
    sockets = _connections.get(user_id, [])
    dead: list[WebSocket] = []
    text = json.dumps(message, default=str)
    for ws in sockets:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.remove(ws)


def register_ws_subscriber() -> None:
    from bus.subscriber import subscribe
    from db.models import Event

    async def push_handler(event: Event) -> None:
        await broadcast_event(
            event.user_id,
            {
                "topic": event.topic,
                "event_id": str(event.event_id),
                "session_id": event.session_id,
                "status": event.status,
                "payload": event.payload,
            },
        )

    for topic in (
        "task.new",
        "planner.start",
        "executor.run",
        "planner.result",
        "planner.retry",
        "manager.result",
        "task.complete",
        "task.failed",
        "manager.line_resolved",
        "manager.time_resolved",
        "manager.context_synced",
        "manager.plan_built",
    ):
        subscribe(topic, push_handler, 20, "ws_subscriber")
