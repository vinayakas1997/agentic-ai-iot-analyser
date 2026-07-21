import logging

from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)

_REDIRECT_MESSAGE = (
    "To confirm this plan, please press the **Go — proceed** button below."
)


async def confirm_redirect(state: ManagerState) -> ManagerState:
    logger.debug("confirm_redirect: starting")
    return {
        **state,
        "analysis_proposals": None,
        "agent_message": _REDIRECT_MESSAGE,
        "phase": "ask",
    }
