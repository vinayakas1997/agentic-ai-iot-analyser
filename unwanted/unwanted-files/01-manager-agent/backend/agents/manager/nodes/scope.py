"""Scope selection interrupt node (numbered machine menu)."""

from agents.manager.debug_log import debug, debug_state
from agents.manager.scope_selection import format_scope_menu
from agents.manager.state import ManagerState


async def ask_scope_selection(state: ManagerState) -> ManagerState:
    debug_state("ask_scope_selection", state)
    slots = state.get("slots") or {}
    msg = format_scope_menu(slots)
    debug("ask_scope_selection", "reply")
    return {
        **state,
        "agent_message": msg,
        "phase": "ask",
        "scope_pending": True,
    }
