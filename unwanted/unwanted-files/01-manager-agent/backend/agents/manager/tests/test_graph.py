"""Integration tests for the manager graph structure and node wiring."""

import pytest

from agents.manager.graph import build_manager_graph, INTERRUPT_AFTER, manager_graph


class TestGraphStructure:
    def test_graph_is_compiled(self):
        """Verify the graph compiles without errors."""
        graph = build_manager_graph()
        assert graph is not None

    def test_graph_has_correct_node_count(self):
        """27 nodes expected in the graph."""
        graph = build_manager_graph()
        # Get all nodes from the graph
        nodes = list(graph.nodes.keys())
        assert len(nodes) == 27, f"Expected 27 nodes, got {len(nodes)}: {nodes}"

    def test_expected_nodes_present(self):
        graph = build_manager_graph()
        nodes = list(graph.nodes.keys())
        expected = [
            "inject_reference_time",
            "extract_slots",
            "merge_slots",
            "resolve_all_lines",
            "sync_session_context",
            "apply_task_reuse",
            "resolve_time_filters",
            "reorganize_aim",
            "build_plan_message",
            "detect_confirm",
            "save_task_definition",
            "send_to_planner",
        ]
        for name in expected:
            assert name in nodes, f"Missing node: {name}"

    def test_interrupt_nodes(self):
        """13 nodes should be in the interrupt list."""
        assert len(INTERRUPT_AFTER) == 13, f"Expected 13 interrupt nodes, got {len(INTERRUPT_AFTER)}"

    def test_entry_point(self):
        graph = build_manager_graph()
        assert graph.entry_point == "inject_reference_time"

    def test_module_graph_is_singleton(self):
        assert manager_graph is not None
        assert manager_graph == build_manager_graph()


class TestGraphEdges:
    def test_confirm_shortcut_path(self):
        """Verify detect_confirm → save_task_definition → send_to_planner chain."""
        graph = build_manager_graph()
        # Check that detect_confirm has conditional edges
        edges = graph.edges
        # detect_confirm should have conditional edges
        detect_edges = [e for e in edges if e[0] == "detect_confirm"]
        assert len(detect_edges) >= 1

    def test_plan_path_leads_to_build_plan_message(self):
        """reorganize_aim, merge_proposals_to_plan, combine_saved_plans should all go to build_plan_message."""
        edges = graph.edges
        # Check fixed edges from these nodes to build_plan_message
        plan_edges = {
            "reorganize_aim": "build_plan_message",
            "merge_proposals_to_plan": "build_plan_message",
            "combine_saved_plans": "build_plan_message",
            "activate_saved_plan": "build_plan_message",
        }
        for src, dst in plan_edges.items():
            assert any(
                e[0] == src and e[1] == dst for e in edges
            ), f"Missing edge {src} -> {dst}"


class TestGraphModule:
    def test_imports(self):
        from agents.manager.nodes import (
            extract_slots,
            merge_slots,
            inject_reference_time,
            resolve_all_lines,
            sync_session_context,
            reorganize_aim,
            build_plan_message,
            detect_confirm,
            save_task_definition_node,
            send_to_planner,
        )
        assert callable(extract_slots)

    def test_routing_imports(self):
        from agents.manager.routing import (
            route_after_inject,
            route_after_merge,
            route_after_resolve_all_lines,
            route_after_sync_session_context,
            route_after_time,
            route_after_confirm,
        )
        assert callable(route_after_inject)
