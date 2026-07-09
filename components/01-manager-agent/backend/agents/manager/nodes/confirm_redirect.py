import logging

from agents.manager.debug_log import debug, debug_state
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)

CONFIRM_REDIRECT_MESSAGE = (
    "I'm in plan mode. To confirm this plan, please press the **Go — proceed** button "
    "or type exactly: go, confirm, yes, proceed, ok"
)


async def confirm_redirect(state: ManagerState) -> ManagerState:
    debug_state("confirm_redirect", state)
    state = {**state, "error": None}
    debug("confirm_redirect", "showing redirect message")
    return {
        **state,
        "agent_message": CONFIRM_REDIRECT_MESSAGE,
        "phase": "plan",
    }
