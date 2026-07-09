import json
import logging
import re

from bus.publisher import publish as publish_event
from bus.subscriber import subscribe
from config import get_settings
from db.models import Event
from llm.client import complete
from agents.manager.session_db import update_session_mode

logger = logging.getLogger(__name__)
settings = get_settings()

_task_results: dict[str, list[dict]] = {}
_task_queries: dict[str, list[str]] = {}
_task_meta: dict[str, dict] = {}


def _base_payload(event: Event) -> dict:
    p = event.payload
    return {
        "task_id": p.get("task_id"),
        "session_id": event.session_id or p.get("session_id"),
        "parent_event_id": str(event.event_id),
    }


def _parse_queries(text: str) -> list[str]:
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            queries = json.loads(match.group())
            if isinstance(queries, list):
                return [str(q) for q in queries[:4]]
    except json.JSONDecodeError:
        pass
    return [
        "df.describe()",
        "df.head(10)",
        "df.columns.tolist()",
    ]


async def _start_planner(event: Event) -> None:
    payload = event.payload
    task_id = payload.get("task_id") or str(event.event_id)
    task = payload.get("data", {}).get("task") or payload.get("task", "")
    data_source = payload.get("data", {}).get("data_source") or payload.get("data_source", "")

    prompt = f"""Plan 3 pandas queries to evaluate this analysis task on a CSV dataframe named df.
Task: {task}
Data source: {data_source}
Return ONLY a JSON array of query strings, e.g. ["df.shape", "df.describe()"]"""

    response = await complete(settings.planner_model, [{"role": "user", "content": prompt}])
    queries = _parse_queries(response)

    _task_queries[task_id] = queries
    _task_results[task_id] = []
    _task_meta[task_id] = {"task": task, "data_source": data_source, "user_id": event.user_id}

    base = _base_payload(event)
    base["data"] = {
        "task": task,
        "data_source": data_source,
        "queries": queries,
        "query": queries[0],
        "query_index": 0,
        "attempt": 0,
        "task_id": task_id,
    }
    base["task_id"] = task_id

    await publish_event("executor.run", event.user_id, base, session_id=event.session_id)


async def _handle_retry(event: Event) -> None:
    payload = event.payload
    data = payload.get("data", {})
    task_id = payload.get("task_id") or data.get("task_id")
    attempt = data.get("attempt", 0) + 1

    if attempt > 3:
        await _finish_with_manager(event, task_id, failed=True, error=data.get("result", {}).get("error", "max retries"))
        return

    prompt = f"""A pandas query failed. Fix the query.
Task: {data.get('task')}
Failed query: {data.get('query')}
Error: {data.get('result', {}).get('error')}
Return ONLY the fixed query string."""

    fixed = await complete(settings.planner_model, [{"role": "user", "content": prompt}])
    query = fixed.strip().strip('"').strip("'")

    base = _base_payload(event)
    base["task_id"] = task_id
    base["data"] = {
        **data,
        "query": query,
        "attempt": attempt,
        "task_id": task_id,
    }

    await publish_event("executor.run", event.user_id, base, session_id=event.session_id)


async def _handle_result(event: Event) -> None:
    payload = event.payload
    data = payload.get("data", {})
    task_id = payload.get("task_id") or data.get("task_id")

    _task_results.setdefault(task_id, []).append(data.get("result", {}))
    queries = _task_queries.get(task_id, [])
    next_index = data.get("query_index", 0) + 1

    if next_index < len(queries):
        base = _base_payload(event)
        meta = _task_meta.get(task_id, {})
        base["task_id"] = task_id
        base["data"] = {
            "task": meta.get("task", ""),
            "data_source": meta.get("data_source", ""),
            "queries": queries,
            "query": queries[next_index],
            "query_index": next_index,
            "attempt": 0,
            "task_id": task_id,
        }
        await publish_event("executor.run", event.user_id, base, session_id=event.session_id)
    else:
        await _finish_with_manager(event, task_id, failed=False)


async def _finish_with_manager(event: Event, task_id: str, failed: bool = False, error: str = "") -> None:
    meta = _task_meta.get(task_id, {})
    base = _base_payload(event)
    base["task_id"] = task_id
    base["data"] = {
        "task": meta.get("task", ""),
        "data_source": meta.get("data_source", ""),
        "results": _task_results.get(task_id, []),
        "failed": failed,
        "error": error,
        "task_id": task_id,
    }
    await publish_event("planner.result", event.user_id, base, session_id=event.session_id)
    _task_results.pop(task_id, None)
    _task_queries.pop(task_id, None)
    _task_meta.pop(task_id, None)


async def handle_start(event: Event) -> None:
    if event.session_id:
        await update_session_mode(event.session_id, event.user_id, "plan")
    await _start_planner(event)


async def handle_retry(event: Event) -> None:
    await _handle_retry(event)


async def handle_result(event: Event) -> None:
    await _handle_result(event)


def register() -> None:
    subscribe("planner.start", handle_start, settings.planner_concurrency, "planner_agent")
    subscribe("planner.retry", handle_retry, settings.planner_concurrency, "planner_agent")
    subscribe("planner.result", handle_result, settings.planner_concurrency, "planner_agent")
