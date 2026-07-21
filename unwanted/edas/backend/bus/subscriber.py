import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from db.models import Event

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]

_handlers: dict[str, list[tuple[Handler, asyncio.Semaphore, str]]] = {}


def subscribe(topic: str, handler: Handler, concurrency_limit: int, agent_name: str) -> None:
    sem = asyncio.Semaphore(concurrency_limit)
    _handlers.setdefault(topic, []).append((handler, sem, agent_name))


def get_handlers() -> dict[str, list[tuple[Handler, asyncio.Semaphore, str]]]:
    return _handlers


async def dispatch(event: Event) -> None:
    entries = _handlers.get(event.topic, [])
    if not entries:
        logger.warning("No handler for topic %s", event.topic)
        return

    tasks = [_run_with_sem(handler, sem, event) for handler, sem, _agent_name in entries]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _run_with_sem(handler: Handler, sem: asyncio.Semaphore, event: Event) -> None:
    async with sem:
        try:
            await handler(event)
        except Exception:
            logger.exception("Handler failed for event %s topic %s", event.event_id, event.topic)
