"""Answer session meta questions from inventory templates."""

from agents.manager.context.meta_responses import answer_session_meta
from agents.manager.context.session_inventory import build_session_inventory
from agents.manager.debug_log import debug, debug_state
from agents.manager.state import ManagerState


async def answer_session_meta_node(state: ManagerState) -> ManagerState:
    debug_state("answer_session_meta", state)
    inventory = state.get("session_inventory") or build_session_inventory(state)
    user_message = state.get("user_message") or ""
    message = answer_session_meta(user_message, inventory)
    debug("answer_session_meta", "reply", topic=inventory.get("phase"))
    return {
        **state,
        "session_inventory": inventory,
        "agent_message": message,
        "phase": "ask",
    }
