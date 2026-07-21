from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.manager.analyst import analyst
from agents.manager.confirm_redirect import confirm_redirect
from agents.manager.router import route_after_analyst, route_after_inject, route_after_tool
from agents.manager.state import ManagerState
from agents.manager.tools import (
    tool_answer_advisory,
    tool_confirm_plan,
    tool_extract_slots,
    tool_fetch_schema,
    tool_generate_plans,
    tool_reorganize_aims,
    tool_resolve_line,
    tool_resolve_time,
)
from agents.manager.time_utils import inject_reference_time

INTERRUPT_AFTER = [
    "tool_answer_advisory",
]

_checkpointer = MemorySaver()


def build_manager_graph():
    graph = StateGraph(ManagerState)

    graph.add_node("inject_reference_time", inject_reference_time)
    graph.add_node("analyst", analyst)
    graph.add_node("confirm_redirect", confirm_redirect)

    graph.add_node("tool_extract_slots", tool_extract_slots)
    graph.add_node("tool_resolve_line", tool_resolve_line)
    graph.add_node("tool_resolve_time", tool_resolve_time)
    graph.add_node("tool_fetch_schema", tool_fetch_schema)
    graph.add_node("tool_reorganize_aims", tool_reorganize_aims)
    graph.add_node("tool_generate_plans", tool_generate_plans)
    graph.add_node("tool_answer_advisory", tool_answer_advisory)
    graph.add_node("tool_confirm_plan", tool_confirm_plan)

    graph.set_entry_point("inject_reference_time")

    graph.add_conditional_edges(
        "inject_reference_time",
        route_after_inject,
        {"analyst": "analyst", "confirm_redirect": "confirm_redirect"},
    )

    graph.add_conditional_edges(
        "analyst",
        route_after_analyst,
        {
            "tool_extract_slots": "tool_extract_slots",
            "tool_resolve_line": "tool_resolve_line",
            "tool_resolve_time": "tool_resolve_time",
            "tool_fetch_schema": "tool_fetch_schema",
            "tool_reorganize_aims": "tool_reorganize_aims",
            "tool_generate_plans": "tool_generate_plans",
            "tool_answer_advisory": "tool_answer_advisory",
            "tool_confirm_plan": "tool_confirm_plan",
            "__end__": END,
        },
    )

    graph.add_conditional_edges(
        "tool_extract_slots", route_after_tool, {"analyst": "analyst", "__end__": END},
    )
    graph.add_conditional_edges(
        "tool_resolve_line", route_after_tool, {"analyst": "analyst", "__end__": END},
    )
    graph.add_conditional_edges(
        "tool_resolve_time", route_after_tool, {"analyst": "analyst", "__end__": END},
    )
    graph.add_conditional_edges(
        "tool_fetch_schema", route_after_tool, {"analyst": "analyst", "__end__": END},
    )
    graph.add_conditional_edges(
        "tool_reorganize_aims", route_after_tool, {"analyst": "analyst", "__end__": END},
    )
    graph.add_conditional_edges(
        "tool_generate_plans", route_after_tool, {"analyst": "analyst", "__end__": END},
    )
    graph.add_conditional_edges(
        "tool_answer_advisory", route_after_tool, {"analyst": "analyst", "__end__": END},
    )
    graph.add_edge("tool_confirm_plan", END)
    graph.add_edge("confirm_redirect", END)

    return graph.compile(checkpointer=_checkpointer, interrupt_after=INTERRUPT_AFTER)


manager_graph = build_manager_graph()
