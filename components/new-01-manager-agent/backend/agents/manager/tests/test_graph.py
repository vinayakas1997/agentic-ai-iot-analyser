"""Integration tests for the manager graph structure and node wiring."""

import pytest

from agents.manager.graph import build_manager_graph, INTERRUPT_AFTER, manager_graph

EXPECTED_NODES = [
    "inject_reference_time",
    "analyst",
    "confirm_redirect",
    "tool_extract_slots",
    "tool_resolve_line",
    "tool_resolve_time",
    "tool_fetch_schema",
    "tool_reorganize_aims",
    "tool_generate_plans",
    "tool_answer_advisory",
    "tool_confirm_plan",
]


def _get_edges(graph):
    """Return list of (source, target) tuples from the compiled graph."""
    raw = graph.get_graph()
    return [(e.source, e.target) for e in raw.edges]


class TestGraphStructure:
    def test_graph_is_compiled(self):
        graph = build_manager_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        graph = build_manager_graph()
        nodes = list(graph.nodes.keys())
        # Compiled graph auto-adds __start__; all expected nodes should be present.
        for name in EXPECTED_NODES:
            assert name in nodes, f"Missing node: {name}"

    def test_interrupt_nodes(self):
        assert INTERRUPT_AFTER == ["tool_answer_advisory"]

    def test_module_graph_is_singleton(self):
        assert manager_graph is not None


class TestGraphEdges:
    def test_start_routes_to_inject_reference_time(self):
        edges = _get_edges(build_manager_graph())
        assert ("__start__", "inject_reference_time") in edges

    def test_inject_reference_time_routes_to_analyst(self):
        edges = _get_edges(build_manager_graph())
        assert ("inject_reference_time", "analyst") in edges

    def test_analyst_routes_to_all_tools(self):
        edges = _get_edges(build_manager_graph())
        tool_nodes = [n for n in EXPECTED_NODES if n.startswith("tool_")]
        for tool_node in tool_nodes:
            assert ("analyst", tool_node) in edges, f"Missing edge analyst -> {tool_node}"

    def test_analyst_can_end(self):
        edges = _get_edges(build_manager_graph())
        assert ("analyst", "__end__") in edges

    def test_tools_loop_back_to_analyst(self):
        edges = _get_edges(build_manager_graph())
        loopback_tools = [
            n for n in EXPECTED_NODES
            if n.startswith("tool_") and n != "tool_confirm_plan"
        ]
        for tool_node in loopback_tools:
            assert (tool_node, "analyst") in edges, f"Missing loopback edge {tool_node} -> analyst"

    def test_tools_can_end(self):
        edges = _get_edges(build_manager_graph())
        loopback_tools = [
            n for n in EXPECTED_NODES
            if n.startswith("tool_") and n != "tool_confirm_plan"
        ]
        for tool_node in loopback_tools:
            assert (tool_node, "__end__") in edges, f"Missing end edge {tool_node} -> __end__"

    def test_confirm_plan_ends(self):
        edges = _get_edges(build_manager_graph())
        assert ("tool_confirm_plan", "__end__") in edges

    def test_confirm_redirect_ends(self):
        edges = _get_edges(build_manager_graph())
        assert ("confirm_redirect", "__end__") in edges


class TestGraphImport:
    def test_analyst_import(self):
        from agents.manager.analyst import analyst
        assert callable(analyst)

    def test_router_import(self):
        from agents.manager.router import route_after_analyst, route_after_tool, route_after_inject
        assert callable(route_after_analyst)
        assert callable(route_after_tool)
        assert callable(route_after_inject)

    def test_tools_import(self):
        from agents.manager.tools import (
            tool_extract_slots,
            tool_resolve_line,
            tool_resolve_time,
            tool_fetch_schema,
            tool_reorganize_aims,
            tool_generate_plans,
            tool_answer_advisory,
            tool_confirm_plan,
        )
        assert callable(tool_extract_slots)
        assert callable(tool_confirm_plan)
