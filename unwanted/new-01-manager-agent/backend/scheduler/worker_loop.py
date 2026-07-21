import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from bus.subscriber import dispatch, get_handlers
from config import get_settings
from db.models import Event
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()

_running = False
_task: asyncio.Task | None = None


async def _claim_pending(limit: int = 20) -> list[Event]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Event)
            .where(Event.status == "pending", Event.execute_at <= datetime.now(timezone.utc))
            .order_by(Event.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        events = list(result.scalars().all())
        for ev in events:
            handler_entries = get_handlers().get(ev.topic, [])
            agent_name = handler_entries[0][2] if handler_entries else "unknown"
            await db.execute(
                update(Event)
                .where(Event.id == ev.id)
                .values(status="running", consumed_by=agent_name, updated_at=datetime.now(timezone.utc))
            )
            ev.status = "running"
            ev.consumed_by = agent_name
            await db.refresh(ev)
        await db.commit()
        for ev in events:
            db.expunge(ev)
        return events


async def _mark_done(event_id, status: str = "done") -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Event)
            .where(Event.event_id == event_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        await db.commit()


async def _cleanup_old_events() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.event_retention_hours)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.status == "done", Event.updated_at < cutoff))
        await db.commit()


async def _poll_once() -> None:
    events = await _claim_pending()
    for ev in events:
        asyncio.create_task(_process_event(ev))


async def _process_event(event: Event) -> None:
    try:
        await dispatch(event)
        await _mark_done(event.event_id, "done")
    except Exception:
        logger.exception("Failed processing event %s", event.event_id)
        await _mark_done(event.event_id, "failed")


async def worker_loop() -> None:
    global _running
    _running = True
    logger.info("Worker loop started")
    while _running:
        try:
            await _poll_once()
            await _cleanup_old_events()
        except Exception:
            logger.exception("Worker poll error")
        await asyncio.sleep(settings.worker_poll_interval_seconds)


async def start_worker() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(worker_loop())


async def stop_worker() -> None:
    global _running, _task
    _running = False
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
