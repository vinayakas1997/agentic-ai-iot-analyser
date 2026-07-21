import logging

from config import get_settings
from agents.manager.graph import manager_graph
from harness.tracer import set_session as _trace_set_session, clear_session as _trace_clear_session, bump_turn as _trace_bump_turn

logger = logging.getLogger(__name__)


def _empty_slots():
    return {
        "line": {"mention": None, "canonical": None, "resolved": False, "source": None, "candidates": []},
        "time": {"raw": None, "start_raw": None, "end_raw": None, "mentioned": False, "start": None, "end": None, "resolved": False, "ambiguous": False, "interpretations": [], "no_filter": False, "parse_error": None, "canonical": None},
        "aim": {"raw": None, "aims": [], "reorganized": False},
        "scope": {"slot_count": 0, "intent_mode": "single", "joint_aim_raw": None, "joint_time_raw": None},
        "line_slots": [],
        "active_line_index": None,
        "dataset_context": {"by_line": {}, "active_line": None, "pending_mentions": [], "pending_exclude": [], "pending_include": []},
    }


def _empty_dataset_context():
    return {"by_line": {}, "active_line": None, "pending_mentions": [], "pending_exclude": [], "pending_include": []}


def _append_turn_to_history(chat_history: list | None, user_message: str, agent_message: str) -> list:
    history = list(chat_history or [])
    if user_message.strip():
        from langchain_core.messages import HumanMessage
        history.append(HumanMessage(content=user_message.strip()))
    if agent_message.strip():
        from langchain_core.messages import AIMessage
        history.append(AIMessage(content=agent_message.strip()))
    return history


def _validate_input(user_message: str, line_name: str) -> str | None:
    settings = get_settings()
    if not user_message or not user_message.strip():
        return "Message cannot be empty."
    if len(user_message) > settings.max_message_length:
        return f"Message too long ({len(user_message)} chars, max {settings.max_message_length})."
    if line_name and len(line_name) > 200:
        return "Line name too long."
    return None


def _is_session_done(phase: str | None, existing: dict | None) -> bool:
    if phase == "done":
        return True
    if existing and existing.get("phase") == "done":
        return True
    return False


def _default_state(existing: dict | None) -> dict:
    base = existing or {}
    slots = dict(base.get("slots") or _empty_slots())
    dataset_context = base.get("dataset_context") or slots.get("dataset_context") or _empty_dataset_context()
    slots["dataset_context"] = dataset_context
    return {
        "reference_now": base.get("reference_now", ""),
        "reference_timezone": base.get("reference_timezone", "UTC"),
        "slots": slots,
        "line_context": base.get("line_context"),
        "plan": base.get("plan"),
        "phase": base.get("phase", "extract"),
        "chat_history": base.get("chat_history", []),
        "task_confirmed": base.get("task_confirmed", False),
        "task_definition": base.get("task_definition"),
        "agent_message": base.get("agent_message", ""),
        "error": base.get("error"),
        "planner_payload": base.get("planner_payload"),
        "analysis_proposals": base.get("analysis_proposals"),
        "selected_proposal_index": base.get("selected_proposal_index"),
        "custom_aims": base.get("custom_aims") or [],
        "explore_phase": base.get("explore_phase"),
        "aim_exploration": base.get("aim_exploration"),
        "explore_context": base.get("explore_context"),
        "dataset_context": base.get("dataset_context"),
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
        "analyst_reasoning": None,
        "tool_to_call": None,
        "tool_result": None,
        "tool_call_count": base.get("tool_call_count", 0),
        "tool_call_history": base.get("tool_call_history", []),
        "proposal_counter": base.get("proposal_counter", 0),
    }


async def run_manager_agent(
    user_id: str,
    session_id: str,
    line_name: str,
    user_message: str,
    existing_state: dict | None = None,
    client: str = "cli",
) -> dict:
    error = _validate_input(user_message, line_name)
    if error:
        logger.warning("Input validation failed for session %s: %s", session_id, error)
        return {
            "agent_message": error,
            "phase": existing_state.get("phase") if existing_state else "extract",
            "error": "validation_error",
        }

    phase = existing_state.get("phase") if existing_state else None
    if _is_session_done(phase, existing_state):
        logger.info("Session %s is already done — rejecting message", session_id)
        return {
            "agent_message": (
                "This analysis session is complete. "
                "Start a new session for a new analysis request."
            ),
            "phase": "done",
            "error": "session_done",
            "planner_payload": (existing_state or {}).get("planner_payload"),
        }

    clean_line = (line_name or "").strip()[:200]
    config = {"configurable": {"thread_id": session_id}}

    state = {
        **_default_state(existing_state),
        "user_id": user_id,
        "session_id": session_id,
        "user_message": user_message.strip(),
        "client": client,
    }
    if clean_line:
        slots = dict(state["slots"])
        line = dict(slots.get("line") or {})
        line["mention"] = clean_line
        slots["line"] = line
        state["slots"] = slots

    _trace_set_session(session_id)
    try:
        result = await manager_graph.ainvoke(state, config)
    finally:
        _trace_bump_turn(session_id)
    result = dict(result)
    result["chat_history"] = _append_turn_to_history(
        result.get("chat_history") or state.get("chat_history"),
        user_message,
        result.get("agent_message") or "",
    )
    return result
