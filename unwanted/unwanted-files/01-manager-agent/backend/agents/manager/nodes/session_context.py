"""Sync session context — registry, time inventory, full session inventory."""

from api.websocket import broadcast_event
from agents.manager.context.session_inventory import build_session_inventory
from agents.manager.context.task_history import load_task_history_for_state
from agents.manager.context.time import build_time_inventory
from agents.manager.debug_log import debug, debug_state
from agents.manager.nodes.registry import sync_registry_context
from agents.manager.state import ManagerState


async def sync_time_context(state: ManagerState) -> dict:
    """Build time_context snapshot from current slots (no side effects)."""
    slots = state.get("slots") or {}
    time_context = build_time_inventory(slots)
    debug("sync_time_context", "done", status=time_context.get("status"))
    return {"time_context": time_context}


async def sync_session_context(state: ManagerState) -> ManagerState:
    """Orchestrator: registry sync, time inventory, session inventory cache."""
    debug_state("sync_session_context", state)
    state = await sync_registry_context(state)
    if state.get("error") == "no_datasets":
        return state

    time_updates = await sync_time_context(state)
    state = {**state, **time_updates}

    task_history = await load_task_history_for_state(state)
    inventory = build_session_inventory(state, task_history=task_history)
    debug(
        "sync_session_context",
        "done",
        phase=inventory.get("phase"),
        missing=inventory.get("missing"),
    )

    slots = state.get("slots") or {}
    line_context = state.get("line_context") or {}
    datasets_list = (line_context.get("datasets") or [])[:3]
    try:
        await broadcast_event(state.get("user_id", ""), {
            "topic": "manager.context_synced",
            "session_id": state.get("session_id", ""),
            "payload": {
                "line": (slots.get("line") or {}).get("canonical"),
                "datasets": [d.get("name") for d in datasets_list if d.get("name")],
                "suggested_aims": line_context.get("suggested_aims", [])[:5],
            },
        })
    except Exception:
        pass

    return {
        **state,
        "session_inventory": inventory,
    }
