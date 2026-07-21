"""Tests for router.py — conditional edge logic for graph routing."""

import pytest

from agents.manager.router import route_after_inject, route_after_analyst, route_after_tool, TOOL_MAP


def _state(**overrides) -> dict:
    state = {
        "user_message": "",
        "phase": "extract",
        "agent_message": None,
        "tool_to_call": None,
        "error": None,
    }
    state.update(overrides)
    return state


class TestRouteAfterInject:
    def test_always_routes_to_analyst(self):
        s = _state()
        assert route_after_inject(s) == "analyst"

    def test_returns_analyst_regardless_of_phase(self):
        for phase in ("extract", "ask", "tool", "man", "done"):
            s = _state(phase=phase)
            assert route_after_inject(s) == "analyst"


class TestRouteAfterAnalyst:
    def test_ends_when_agent_message_present(self):
        s = _state(agent_message="hello")
        assert route_after_analyst(s) == "__end__"

    def test_ends_when_no_tool(self):
        s = _state(agent_message="", tool_to_call=None)
        assert route_after_analyst(s) == "__end__"

    def test_routes_to_known_tool(self):
        for tool_name, node_name in TOOL_MAP.items():
            s = _state(agent_message="", tool_to_call=tool_name)
            assert route_after_analyst(s) == node_name

    def test_ends_on_unknown_tool(self):
        s = _state(agent_message="", tool_to_call="nonexistent_tool")
        assert route_after_analyst(s) == "__end__"


class TestRouteAfterTool:
    def test_ends_when_tool_responded(self):
        s = _state(agent_message="tool finished", phase="ask")
        assert route_after_tool(s) == "__end__"

    def test_loops_to_analyst_when_no_response(self):
        s = _state(agent_message="", phase="tool")
        assert route_after_tool(s) == "analyst"


class TestToolMap:
    def test_all_expected_tools_present(self):
        expected = [
            "extract_slots",
            "resolve_line",
            "resolve_time",
            "fetch_schema",
            "reorganize_aims",
            "generate_plans",
            "answer_advisory",
            "confirm_plan",
        ]
        for tool in expected:
            assert tool in TOOL_MAP

    def test_all_nodes_prefixed_with_tool(self):
        for node in TOOL_MAP.values():
            assert node.startswith("tool_")
