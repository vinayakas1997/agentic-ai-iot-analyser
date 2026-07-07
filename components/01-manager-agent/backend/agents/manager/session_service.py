"""Orchestrate manager turns with DB-backed session state."""

from agents.manager.runner import run_manager_agent
from agents.manager.session_db import (
    append_chat_turn,
    create_session,
    fork_session,
    get_session_row,
    load_chat_messages,
    load_chat_turns,
    load_session,
    list_sessions,
    next_turn_index,
    reopen_session,
    save_session,
)
from agents.manager.session_store import (
    build_turn_snapshot,
    canonical_line_from_state,
    format_turn_response,
)


async def run_session_turn(
    user_id: str,
    session_id: str,
    user_message: str,
    line_name: str = "",
) -> dict:
    """Load state, run one graph turn, persist session and chat rows."""
    row = await get_session_row(user_id, session_id)
    if not row:
        raise ValueError("session_not_found")

    existing = await load_session(user_id, session_id)
    result = await run_manager_agent(
        user_id=user_id,
        session_id=session_id,
        line_name=line_name,
        user_message=user_message,
        existing_state=existing,
        client="web",
    )
    await save_session(user_id, session_id, result)

    snapshot = build_turn_snapshot(result)
    turn_index = await next_turn_index(user_id, session_id)
    await append_chat_turn(
        user_id=user_id,
        session_id=session_id,
        user_message=user_message,
        agent_message=result.get("agent_message") or "",
        line_name=canonical_line_from_state(result),
        node=None,
        turn_index=turn_index,
        ui_snapshot=snapshot["ui"],
        schema_snapshot=snapshot["schema"],
    )
    return format_turn_response(result, session_id, turn_index=turn_index)


async def get_session_detail(user_id: str, session_id: str) -> dict | None:
    row = await get_session_row(user_id, session_id)
    if not row:
        return None
    turns = await load_chat_turns(user_id, session_id)
    messages = await load_chat_messages(user_id, session_id)

    latest_ui = turns[-1]["ui"] if turns else None
    latest_schema = turns[-1]["schema"] if turns else None

    return {
        "session": {
            "session_id": row.session_id,
            "line_name": row.line_name,
            "phase": row.phase,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        },
        "turns": turns,
        "messages": messages,
        "ui": latest_ui,
        "schema": latest_schema,
    }


async def reopen_session_turn(user_id: str, session_id: str) -> dict:
    """Reopen a done session. Raises ValueError if planner already picked it up."""
    await reopen_session(user_id, session_id)
    detail = await get_session_detail(user_id, session_id)
    if not detail:
        raise ValueError("session_not_found")
    return detail


async def fork_session_turn(user_id: str, session_id: str) -> str:
    """Fork an existing session into a new session."""
    return await fork_session(user_id, session_id)


__all__ = [
    "create_session",
    "fork_session_turn",
    "get_session_detail",
    "list_sessions",
    "reopen_session_turn",
    "run_session_turn",
]
