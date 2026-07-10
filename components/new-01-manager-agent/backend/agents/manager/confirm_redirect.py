import logging

from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)

_REDIRECT_MESSAGE = (
    "I see you're trying to confirm or select an option. "
    "To confirm this plan, please press the **Go — proceed** button "
    "or type exactly: go, confirm, yes, proceed, ok"
)


async def confirm_redirect(state: ManagerState) -> ManagerState:
    logger.debug("confirm_redirect: starting")
    return {
        **state,
        "analysis_proposals": None,
        "agent_message": _REDIRECT_MESSAGE,
        "phase": "plan",
    }
