from agents.manager.debug_log import debug_route
from agents.manager.state import ManagerState

TOOL_MAP = {
    "extract_slots": "tool_extract_slots",
    "resolve_line": "tool_resolve_line",
    "resolve_time": "tool_resolve_time",
    "fetch_schema": "tool_fetch_schema",
    "reorganize_aims": "tool_reorganize_aims",
    "generate_plans": "tool_generate_plans",
    "answer_advisory": "tool_answer_advisory",
    "confirm_plan": "tool_confirm_plan",
}

_CONFIRM_WORDS = ("go", "confirm", "yes", "proceed", "ok")


def is_confirm_message(user_msg: str) -> bool:
    return user_msg in _CONFIRM_WORDS


def is_confirm_like_message(user_msg: str) -> bool:
    for w in _CONFIRM_WORDS:
        if w in user_msg:
            return True
    return False


def route_after_inject(state: ManagerState) -> str:
    user_msg = (state.get("user_message") or "").lower().strip()
    if state.get("phase") == "plan" and is_confirm_message(user_msg):
        debug_route("route_after_inject", "analyst (confirm)")
        return "analyst"
    if state.get("phase") == "plan" and is_confirm_like_message(user_msg):
        debug_route("route_after_inject", "confirm_redirect")
        return "confirm_redirect"
    debug_route("route_after_inject", "analyst")
    return "analyst"


def route_after_analyst(state: ManagerState) -> str:
    if state.get("agent_message"):
        debug_route("route_after_analyst", "__end__ (responded)")
        return "__end__"

    tool = state.get("tool_to_call")
    if not tool:
        debug_route("route_after_analyst", "__end__ (no tool)")
        return "__end__"

    node = TOOL_MAP.get(tool)
    if node:
        debug_route("route_after_analyst", node)
        return node

    debug_route("route_after_analyst", "__end__ (unknown tool)")
    return "__end__"


def route_after_tool(state: ManagerState) -> str:
    if state.get("agent_message"):
        debug_route("route_after_tool", "__end__ (tool responded)")
        return "__end__"
    debug_route("route_after_tool", "analyst (loop back)")
    return "analyst"
