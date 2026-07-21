import logging

from bus.subscriber import subscribe
from sqlalchemy import insert

from db.models import Event, Result
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def handle_complete(event: Event) -> None:
    data = event.payload.get("data", {})
    async with AsyncSessionLocal() as db:
        await db.execute(
            insert(Result).values(
                user_id=event.user_id,
                session_id=event.session_id,
                event_id=event.event_id,
                task=data.get("task"),
                result=data,
                status=data.get("status", "complete"),
            )
        )
        await db.commit()


async def handle_failed(event: Event) -> None:
    data = event.payload.get("data", {})
    async with AsyncSessionLocal() as db:
        await db.execute(
            insert(Result).values(
                user_id=event.user_id,
                session_id=event.session_id,
                event_id=event.event_id,
                task=data.get("task"),
                result=data,
                status="failed",
            )
        )
        await db.commit()


def register() -> None:
    subscribe("task.complete", handle_complete, 5, "db_subscriber")
    subscribe("task.failed", handle_failed, 5, "db_subscriber")
