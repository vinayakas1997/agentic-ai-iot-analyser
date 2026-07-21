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

def route_after_inject(state: ManagerState) -> str:
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
