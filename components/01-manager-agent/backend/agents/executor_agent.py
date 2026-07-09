import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from bus.publisher import publish as publish_event
from bus.subscriber import subscribe
from config import get_settings
from data.data_handler import DataHandler
from db.models import Event
from agents.manager.session_db import get_session_mode, update_session_mode

logger = logging.getLogger(__name__)
settings = get_settings()
_handler = DataHandler()


def _base_payload(event: Event) -> dict:
    p = event.payload
    return {
        "task_id": p.get("task_id"),
        "session_id": event.session_id or p.get("session_id"),
        "parent_event_id": str(event.event_id),
        "user_id": event.user_id,
    }


async def handle(event: Event) -> None:
    payload = event.payload
    data_source = payload.get("data_source", "")
    query = payload.get("query", "")

    try:
        df = _handler.load(data_source)
        result = _handler.run_query(df, query)
    except Exception as e:
        result = {"success": False, "error": str(e), "error_type": type(e).__name__}

    base = _base_payload(event)
    base["data"] = {
        "query": query,
        "query_index": payload.get("query_index", 0),
        "result": result,
    }

    if event.session_id:
        current_mode = await get_session_mode(event.session_id, event.user_id)
        if current_mode == "plan":
            await update_session_mode(event.session_id, event.user_id, "exe")

    if result.get("success"):
        await publish_event(
            "planner.result",
            event.user_id,
            base,
            session_id=event.session_id,
        )
    else:
        attempt = payload.get("attempt", 0)
        base["data"]["attempt"] = attempt
        base["data"]["queries"] = payload.get("queries", [])
        base["data"]["task"] = payload.get("task", "")
        execute_at = None
        if attempt < 3:
            execute_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        await publish_event(
            "planner.retry",
            event.user_id,
            base,
            session_id=event.session_id,
            execute_at=execute_at,
        )


def register() -> None:
    subscribe("executor.run", handle, settings.executor_concurrency, "executor_agent")
