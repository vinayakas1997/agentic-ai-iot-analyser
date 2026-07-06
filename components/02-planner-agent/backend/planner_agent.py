"""Planner Agent — subscribes to planner.start events from the Manager Agent.

Receives structured planner_payload (line, time range, aims, datasets, join catalog),
plans concrete pandas/analysis queries, and dispatches them to the Executor Agent
via executor.run events on the bus.
"""

import json
import logging
import re

from bus.publisher import publish as publish_event
from bus.subscriber import subscribe
from config import get_settings
from db.models import Event
from llm.client import complete

logger = logging.getLogger(__name__)
settings = get_settings()

_task_state: dict[str, dict] = {}


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
                return [str(q) for q in queries[:settings.max_queries_per_task]]
    except json.JSONDecodeError:
        pass
    return ["df.describe()", "df.head(10)"]


def _build_planner_prompt(payload: dict) -> str:
    """Build a prompt for the planner LLM from the manager's planner_payload."""
    task_def = payload.get("task_definition") or {}
    aims = task_def.get("aims") or payload.get("aims") or []
    time_range = task_def.get("time_range") or payload.get("time_range")
    datasets = payload.get("dataset_schemas") or payload.get("datasets") or []
    joins = payload.get("join_catalog") or []

    context = f"Line: {payload.get('line_name', '?')}\n"
    if time_range:
        context += f"Time: {time_range.get('start')} to {time_range.get('end')}\n"
    if datasets:
        names = [d.get("dataset_name", "?") for d in datasets[:5]]
        context += f"Datasets: {', '.join(names)}\n"
    if joins:
        context += f"Known joins: {json.dumps(joins, indent=2)}\n"

    aims_text = "\n".join(f"- {a}" for a in aims) if aims else "(no aims specified)"
    return (
        f"Plan up to {settings.max_queries_per_task} pandas queries to analyze this IoT data.\n\n"
        f"{context}\n"
        f"Analysis aims:\n{aims_text}\n\n"
        "Return ONLY a JSON array of query strings that can be run on a Pandas DataFrame 'df'. "
        "Each query should be a single pandas expression. "
        "Example: [\"df['temperature'].mean()\", \"df.groupby('hour')['pressure'].std()\"]"
    )


async def _start_planner(event: Event) -> None:
    """Handle planner.start — receive payload, plan queries, kick off executor."""
    payload = event.payload
    task_id = payload.get("task_id") or str(event.event_id)
    session_id = event.session_id or payload.get("session_id", "")

    logger.info("Planner received task for line=%s session=%s",
                payload.get("line_name"), session_id)

    prompt = _build_planner_prompt(payload)
    try:
        response = await complete(settings.planner_model, [{"role": "user", "content": prompt}])
        queries = _parse_queries(response)
    except Exception as exc:
        logger.error("LLM planning failed for task %s: %s", task_id, exc)
        queries = ["df.describe()", "df.head(10)"]

    if not queries:
        queries = ["df.describe()"]

    _task_state[task_id] = {
        "payload": payload,
        "queries": queries,
        "results": [],
        "current_index": 0,
        "session_id": session_id,
        "user_id": event.user_id,
    }

    base = _base_payload(event)
    base["task_id"] = task_id
    base["data"] = {
        "task": payload.get("task_definition", {}),
        "line_name": payload.get("line_name"),
        "datasets_in_scope": payload.get("datasets_in_scope", []),
        "queries": queries,
        "query": queries[0],
        "query_index": 0,
        "attempt": 0,
    }
    logger.info("Publishing executor.run for task %s query 0/%d: %s",
                task_id, len(queries), queries[0][:80])
    await publish_event("executor.run", event.user_id, base, session_id=session_id)


async def _handle_retry(event: Event) -> None:
    """Handle planner.retry — fix a failed query and retry."""
    payload = event.payload
    data = payload.get("data", {})
    task_id = payload.get("task_id") or data.get("task_id")
    attempt = data.get("attempt", 0) + 1

    if attempt > settings.max_retries:
        logger.warning("Task %s failed after %d retries", task_id, settings.max_retries)
        await _finish_with_manager(event, task_id, failed=True,
                                   error=data.get("result", {}).get("error", "max retries"))
        return

    prompt = (
        f"A pandas query failed. Fix it.\n"
        f"Failed query: {data.get('query')}\n"
        f"Error: {data.get('result', {}).get('error')}\n"
        f"Return ONLY the fixed query string."
    )
    try:
        fixed = await complete(settings.planner_model, [{"role": "user", "content": prompt}])
        query = fixed.strip().strip('"').strip("'")
    except Exception as exc:
        logger.error("Retry LLM failed for task %s: %s", task_id, exc)
        query = data.get("query", "")

    base = _base_payload(event)
    base["task_id"] = task_id
    state = _task_state.get(task_id, {})
    queries = state.get("queries", [data.get("query", "")])
    base["data"] = {
        **data,
        "query": query,
        "attempt": attempt,
        "queries": queries,
    }
    await publish_event("executor.run", event.user_id, base, session_id=event.session_id)


async def _handle_result(event: Event) -> None:
    """Handle executor.result — collect result, dispatch next query or finish."""
    payload = event.payload
    data = payload.get("data", {})
    task_id = payload.get("task_id") or data.get("task_id")

    state = _task_state.get(task_id)
    if not state:
        logger.warning("Received result for unknown task %s", task_id)
        return

    result = data.get("result", {})
    state["results"].append(result)
    state["current_index"] += 1
    next_index = state["current_index"]
    queries = state["queries"]

    if next_index < len(queries):
        base = _base_payload(event)
        base["task_id"] = task_id
        base["data"] = {
            "task": data.get("task", state.get("payload", {}).get("task_definition", {})),
            "line_name": state["payload"].get("line_name"),
            "queries": queries,
            "query": queries[next_index],
            "query_index": next_index,
            "attempt": 0,
        }
        logger.info("Publishing executor.run for task %s query %d/%d",
                    task_id, next_index, len(queries))
        await publish_event("executor.run", event.user_id, base,
                            session_id=state.get("session_id"))
    else:
        await _finish_with_manager(event, task_id, failed=False)


async def _finish_with_manager(event: Event, task_id: str, failed: bool = False, error: str = "") -> None:
    state = _task_state.pop(task_id, {})
    base = _base_payload(event)
    base["task_id"] = task_id
    base["data"] = {
        "task": state.get("payload", {}).get("task_definition", {}),
        "line_name": state.get("payload", {}).get("line_name"),
        "results": state.get("results", []),
        "failed": failed,
        "error": error,
    }
    logger.info("Publishing planner.result for task %s (failed=%s)", task_id, failed)
    await publish_event("planner.result", event.user_id, base,
                        session_id=state.get("session_id"))


async def handle_start(event: Event) -> None:
    await _start_planner(event)


async def handle_retry(event: Event) -> None:
    await _handle_retry(event)


async def handle_result(event: Event) -> None:
    await _handle_result(event)


def register() -> None:
    subscribe("planner.start", handle_start, settings.planner_concurrency, "planner_agent")
    subscribe("planner.retry", handle_retry, settings.planner_concurrency, "planner_agent")
    subscribe("planner.result", handle_result, settings.planner_concurrency, "planner_agent")


if __name__ == "__main__":
    import asyncio
    from scheduler.worker_loop import run_worker

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    register()
    logger.info("Planner agent registered. Starting worker loop...")
    asyncio.run(run_worker(agent_name="planner_agent"))
