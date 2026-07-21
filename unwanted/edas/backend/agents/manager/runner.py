from agents.manager.chat_memory import append_turn_to_history
from agents.manager.graph import manager_graph
from agents.manager.registry_context import empty_dataset_context
from agents.manager.slots import empty_slots
from config import apply_runtime_env
from harness.tracer import set_session as _trace_set_session, clear_session as _trace_clear_session, bump_turn as _trace_bump_turn


def _default_state(existing: dict | None) -> dict:
    base = existing or {}
    slots = dict(base.get("slots") or empty_slots())
    dataset_context = base.get("dataset_context") or slots.get("dataset_context") or empty_dataset_context()
    slots["dataset_context"] = dataset_context
    return {
        "reference_now": base.get("reference_now", ""),
        "reference_timezone": base.get("reference_timezone", "UTC"),
        "slots": slots,
        "missing": base.get("missing", []),
        "line_context": base.get("line_context"),
        "plan": base.get("plan"),
        "phase": base.get("phase", "extract"),
        "chat_history": base.get("chat_history", []),
        "task_confirmed": base.get("task_confirmed", False),
        "task_definition": base.get("task_definition"),
        "agent_message": base.get("agent_message", ""),
        "error": base.get("error"),
        "planner_payload": base.get("planner_payload"),
        "wants_suggested_aims": base.get("wants_suggested_aims", False),
        "analysis_proposals": base.get("analysis_proposals"),
        "explore_phase": base.get("explore_phase"),
        "aim_exploration": base.get("aim_exploration"),
        "explore_context": base.get("explore_context"),
        "dataset_context": base.get("dataset_context"),
        "registry_sync_target": base.get("registry_sync_target"),
        "time_context": base.get("time_context"),
        "session_inventory": base.get("session_inventory"),
        "session_intent": base.get("session_intent"),
        "verification_context": base.get("verification_context"),
        "reuse_alias": base.get("reuse_alias"),
        "saved_plans": base.get("saved_plans") or [],
        "session_goal": base.get("session_goal"),
        "user_explore_intent": base.get("user_explore_intent"),
        "scope_selection": base.get("scope_selection"),
        "scope_pending": bool(base.get("scope_pending")),
        "iot_column_wishes": base.get("iot_column_wishes") or [],
    }


async def run_manager_agent(
    user_id: str,
    session_id: str,
    line_name: str,
    user_message: str,
    existing_state: dict | None = None,
    client: str = "cli",
) -> dict:
    """Run one conversational turn of the manager graph."""
    apply_runtime_env()
    config = {"configurable": {"thread_id": session_id}}

    state = {
        **_default_state(existing_state),
        "user_id": user_id,
        "session_id": session_id,
        "user_message": user_message,
        "client": client,
    }
    if line_name.strip():
        slots = dict(state["slots"])
        line = dict(slots.get("line") or {})
        line["mention"] = line_name.strip()
        slots["line"] = line
        state["slots"] = slots

    _trace_set_session(session_id)
    try:
        result = await manager_graph.ainvoke(state, config)
    finally:
        _trace_bump_turn(session_id)
    result = dict(result)
    result["chat_history"] = append_turn_to_history(
        result.get("chat_history") or state.get("chat_history"),
        user_message,
        result.get("agent_message") or "",
    )
    return result
