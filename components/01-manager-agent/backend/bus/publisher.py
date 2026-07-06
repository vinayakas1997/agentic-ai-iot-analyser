import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select, update

from db.models import Event
from db.session import AsyncSessionLocal


async def publish(
    topic: str,
    user_id: str,
    payload: dict[str, Any],
    session_id: str | None = None,
    execute_at: datetime | None = None,
) -> uuid.UUID:
    event_id = uuid.uuid4()
    when = execute_at or datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        await db.execute(
            insert(Event).values(
                event_id=event_id,
                topic=topic,
                user_id=user_id,
                session_id=session_id,
                payload=payload,
                status="pending",
                execute_at=when,
            )
        )
        await db.commit()

    return event_id


async def get_event(event_id: uuid.UUID) -> Event | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Event).where(Event.event_id == event_id))
        return result.scalar_one_or_none()
