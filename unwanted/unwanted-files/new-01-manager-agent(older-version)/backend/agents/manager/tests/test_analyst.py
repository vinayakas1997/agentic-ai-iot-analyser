"""Tests for analyst.py — deterministic routing, circuit breaker, confirm pre-check."""

import pytest
from unittest.mock import AsyncMock, patch

from agents.manager.state import ManagerState
from agents.manager.analyst import _handle_confirm, _detect_tool_loop


class TestHandleConfirm:
    """Unit tests for _handle_confirm (no LLM involvement)."""

    def make_state(self, **overrides) -> ManagerState:
        base: ManagerState = {
            "user_id": "test",
            "session_id": "test-session",
            "user_message": "",
            "reference_now": "2026-07-15T12:00:00Z",
            "reference_timezone": "UTC",
            "slots": {
                "line": {"mention": None, "canonical": "FRUITS_TEST", "resolved": True},
                "time": {"mentioned": False, "resolved": False, "no_filter": True},
                "aim": {"raw": None, "aims": [], "reorganized": False},
                "scope": {},
                "line_slots": [],
                "active_line_index": None,
                "dataset_context": {},
            },
            "line_context": {"suggested_aims": []},
            "plan": None,
            "dataset_context": None,
            "phase": "ask",
            "chat_history": [],
            "task_confirmed": False,
            "task_definition": None,
            "planner_payload": None,
            "agent_message": "",
            "error": None,
            "analyst_reasoning": None,
            "tool_to_call": None,
            "tool_result": None,
            "saved_plans": [],
            "session_goal": None,
            "analysis_proposals": [{"id": 1, "title": "Test Plan", "aims": ["test aim"], "what_you_might_see": "test benefits"}],
            "explore_phase": None,
            "explore_iteration": 0,
            "seen_proposal_titles": [],
            "session_intent": None,
            "verification_context": None,
            "reuse_alias": None,
            "scope_selection": None,
            "scope_pending": False,
            "iot_column_wishes": [],
            "session_inventory": None,
            "explore_context": None,
            "aim_exploration": None,
            "user_explore_intent": None,
            "selected_suggested_aim": None,
            "tool_call_count": 0,
            "tool_call_history": [],
            "proposal_counter": 1,
            "custom_aims": [],
        }
        base.update(overrides)
        if "proposal_counter" not in overrides and "analysis_proposals" in overrides:
            base["proposal_counter"] = len(overrides["analysis_proposals"])
        return base

    def make_session_json(self, **overrides) -> dict:
        return {
            "phase": "ask",
            "last_tool_output": None,
            "tool_call_count": 0,
            "schema_fetched": True,
            "line": {"mention": None, "canonical": "FRUITS_TEST", "resolved": True, "source": "line_name"},
            "time": {"mentioned": False, "resolved": False},
            "aim": {"raw": None, "aims": [], "reorganized": False},
            "scope": {},
            "line_slots": [],
            "active_line_index": None,
            "has_plan": False,
            "plan": None,
            "session_goal": None,
            "saved_plans": [],
            **overrides,
        }

    def test_confirm_proceeds_to_execution(self):
        """__confirm__ should set tool_to_call='confirm_plan' and phase='tool'."""
        state = self.make_state()
        session_json = self.make_session_json()
        result = _handle_confirm(state, "__confirm__", session_json)
        assert result["tool_to_call"] == "confirm_plan"
        assert result["phase"] == "tool"

    def test_confirm_n_selects_proposal(self):
        """confirm 1 should narrow proposals to [selected] and show a review card."""
        proposals = [
            {"id": 1, "title": "Cost Analysis", "aims": ["average cost by fruit"], "what_you_might_see": "Cost data", "display_number": 1},
            {"id": 2, "title": "Sales Report", "aims": ["sales by region"], "what_you_might_see": "Sales data", "display_number": 2},
        ]
        state = self.make_state(analysis_proposals=proposals)
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm 1", session_json)

        assert result["tool_to_call"] is None
        assert result["phase"] == "ask"
        assert result["plan"] is not None
        assert result["plan"]["aims"] == ["average cost by fruit"]
        assert len(result["analysis_proposals"]) == 2
        assert "Cost Analysis" in result["agent_message"]

    def test_confirm_n_selects_second_proposal(self):
        """confirm 2 should pick the second proposal."""
        proposals = [
            {"id": 1, "title": "Cost", "aims": ["cost"], "what_you_might_see": "", "display_number": 1},
            {"id": 2, "title": "Sales", "aims": ["sales"], "what_you_might_see": "", "display_number": 2},
        ]
        state = self.make_state(analysis_proposals=proposals)
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm 2", session_json)
        assert result["plan"]["aims"] == ["sales"]
        assert len(result["analysis_proposals"]) == 2
        assert result["analysis_proposals"][1]["title"] == "Sales"

    def test_confirm_n_invalid_index_shows_error(self):
        """confirm 99 with only 2 proposals should produce an error message."""
        proposals = [
            {"id": 1, "title": "Cost", "aims": ["cost"], "what_you_might_see": "", "display_number": 1},
            {"id": 2, "title": "Sales", "aims": ["sales"], "what_you_might_see": "", "display_number": 2},
        ]
        state = self.make_state(analysis_proposals=proposals)
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm 99", session_json)
        assert "Invalid" in result["agent_message"]
        assert result["phase"] == "ask"

    def test_confirm_n_zero_index(self):
        """confirm 0 should be treated as invalid (1-indexed)."""
        proposals = [
            {"id": 1, "title": "Cost", "aims": ["cost"], "what_you_might_see": "", "display_number": 1},
        ]
        state = self.make_state(analysis_proposals=proposals)
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm 0", session_json)
        assert "Invalid" in result["agent_message"]

    def test_confirm_n_no_proposals(self):
        """confirm 1 with no proposals should show error."""
        state = self.make_state(analysis_proposals=[])
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm 1", session_json)
        assert "Invalid" in result["agent_message"]

    def test_confirm_n_selects_suggested_aim(self):
        """confirm 1 should match a suggested aim when no proposals exist."""
        suggested_aims = [
            {"aim": "cost analysis", "dataset": "fruits", "role": "primary", "kpi_value": "", "display_number": 1},
            {"aim": "sales report", "dataset": "fruits", "role": "primary", "kpi_value": "", "display_number": 2},
        ]
        state = self.make_state(
            analysis_proposals=[],
            line_context={"suggested_aims": suggested_aims},
        )
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm 1", session_json)
        assert result["tool_to_call"] == "generate_plans"
        assert result["selected_suggested_aim"] == "cost analysis"
        assert result["user_message"] == "cost analysis"
        assert result["phase"] == "tool"

    def test_confirm_n_selects_custom_aim(self):
        """confirm 3 should match a custom aim when no proposals or suggested aims match."""
        custom_aims = [
            {"aim": "cost trends", "display_number": 3},
        ]
        state = self.make_state(
            analysis_proposals=[],
            line_context={"suggested_aims": []},
            custom_aims=custom_aims,
        )
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm 3", session_json)
        assert result["tool_to_call"] == "generate_plans"
        assert result["selected_suggested_aim"] == "cost trends"
        assert result["user_message"] == "cost trends"
        assert result["phase"] == "tool"

    def test_non_confirm_message_unchanged(self):
        """A non-confirm message should be left alone."""
        state = self.make_state()
        session_json = self.make_session_json()
        result = _handle_confirm(state, "confirm", session_json)
        assert result["agent_message"] is not None
        assert "Go — proceed" in result["agent_message"]
        assert result["phase"] == "ask"


class TestDetectToolLoop:
    def make_state(self, history: list[str] | None = None, **overrides) -> ManagerState:
        base: ManagerState = {
            "user_id": "test",
            "session_id": "test-session",
            "user_message": "",
            "reference_now": "2026-07-15T12:00:00Z",
            "reference_timezone": "UTC",
            "slots": {
                "line": {"mention": None, "canonical": None, "resolved": False},
                "time": {"mentioned": False, "resolved": False, "no_filter": True},
                "aim": {"raw": None, "aims": [], "reorganized": False},
                "scope": {},
                "line_slots": [],
                "active_line_index": None,
                "dataset_context": {},
            },
            "line_context": {"suggested_aims": []},
            "plan": None,
            "dataset_context": None,
            "phase": "extract",
            "chat_history": [],
            "task_confirmed": False,
            "task_definition": None,
            "planner_payload": None,
            "agent_message": "",
            "error": None,
            "analyst_reasoning": None,
            "tool_to_call": None,
            "tool_result": None,
            "saved_plans": [],
            "session_goal": None,
            "analysis_proposals": None,
            "explore_phase": None,
            "explore_iteration": 0,
            "seen_proposal_titles": [],
            "session_intent": None,
            "verification_context": None,
            "reuse_alias": None,
            "scope_selection": None,
            "scope_pending": False,
            "iot_column_wishes": [],
            "session_inventory": None,
            "explore_context": None,
            "aim_exploration": None,
            "user_explore_intent": None,
            "selected_suggested_aim": None,
            "tool_call_count": 3,
            "tool_call_history": history or [],
        }
        base.update(overrides)
        return base

    def make_session_json(self, **overrides) -> dict:
        return {
            "phase": "extract",
            "last_tool_output": None,
            "tool_call_count": 3,
            "schema_fetched": False,
            "line": {"mention": None, "canonical": None, "resolved": False},
            "time": {"mentioned": False, "resolved": False},
            "aim": {"raw": None, "aims": [], "reorganized": False},
            "scope": {},
            "line_slots": [],
            "active_line_index": None,
            "has_plan": False,
            "plan": None,
            "session_goal": None,
            "saved_plans": [],
            **overrides,
        }

    def test_short_history_no_loop(self):
        """History with <3 entries should not trigger."""
        state = self.make_state(history=["extract_slots"])
        session_json = self.make_session_json()
        assert _detect_tool_loop(state, session_json) is None

    def test_different_tools_no_loop(self):
        """Different consecutive tools should not trigger."""
        state = self.make_state(history=["extract_slots", "resolve_line", "fetch_schema"])
        session_json = self.make_session_json()
        assert _detect_tool_loop(state, session_json) is None

    def test_same_tool_three_times_triggers_loop(self):
        """3x extract_slots with no progress should trigger."""
        state = self.make_state(history=["extract_slots", "extract_slots", "extract_slots"])
        session_json = self.make_session_json()
        reason = _detect_tool_loop(state, session_json)
        assert reason is not None
        assert "production line" in reason.lower()

    def test_same_tool_with_progress_no_loop(self):
        """3x same tool but line resolved + schema fetched = making progress, not a loop."""
        state = self.make_state(
            history=["extract_slots", "extract_slots", "extract_slots"],
            slots={
                "line": {"mention": "FRUITS_TEST", "canonical": "FRUITS_TEST", "resolved": True},
                "time": {"mentioned": False, "resolved": False, "no_filter": True},
                "aim": {"raw": None, "aims": [], "reorganized": False},
                "scope": {},
                "line_slots": [],
                "active_line_index": None,
                "dataset_context": {},
            },
        )
        session_json = self.make_session_json(schema_fetched=True)
        assert _detect_tool_loop(state, session_json) is None

    def test_same_extract_slots_with_mention_uses_name(self):
        """Loop on extract_slots with a line mention should include the name in the message."""
        state = self.make_state(
            history=["extract_slots", "extract_slots", "extract_slots"],
            slots={
                "line": {"mention": "Vinayaka", "canonical": None, "resolved": False},
                "time": {"mentioned": False, "resolved": False, "no_filter": True},
                "aim": {"raw": None, "aims": [], "reorganized": False},
                "scope": {},
                "line_slots": [],
                "active_line_index": None,
                "dataset_context": {},
            },
        )
        session_json = self.make_session_json()
        reason = _detect_tool_loop(state, session_json)
        assert reason is not None
        assert "Vinayaka" in reason


@pytest.mark.asyncio
class TestAnalystConfirmPreCheck:
    """Verify the pre-check intercepts confirm messages before the LLM call."""

    async def test_confirm_intercepted_before_llm(self):
        """When message is __confirm__, the LLM should NOT be called."""
        from agents.manager.analyst import analyst
        mock_llm = AsyncMock()

        state: ManagerState = {
            "user_id": "test",
            "session_id": "test-session",
            "user_message": "__confirm__",
            "reference_now": "2026-07-15T12:00:00Z",
            "reference_timezone": "UTC",
            "slots": {
                "line": {"mention": None, "canonical": "FRUITS_TEST", "resolved": True},
                "time": {"mentioned": False, "resolved": False, "no_filter": True},
                "aim": {"raw": None, "aims": [], "reorganized": False},
                "scope": {},
                "line_slots": [],
                "active_line_index": None,
                "dataset_context": {},
            },
            "line_context": {"suggested_aims": []},
            "plan": None,
            "dataset_context": None,
            "phase": "ask",
            "chat_history": [],
            "task_confirmed": False,
            "task_definition": None,
            "planner_payload": None,
            "agent_message": "",
            "error": None,
            "analyst_reasoning": None,
            "tool_to_call": None,
            "tool_result": None,
            "saved_plans": [],
            "session_goal": None,
            "analysis_proposals": [{"id": 1, "title": "Test", "aims": ["test aim"], "what_you_might_see": ""}],
            "explore_phase": None,
            "explore_iteration": 0,
            "seen_proposal_titles": [],
            "session_intent": None,
            "verification_context": None,
            "reuse_alias": None,
            "scope_selection": None,
            "scope_pending": False,
            "iot_column_wishes": [],
            "session_inventory": None,
            "explore_context": None,
            "aim_exploration": None,
            "user_explore_intent": None,
            "selected_suggested_aim": None,
            "tool_call_count": 0,
            "tool_call_history": [],
        }

        with patch("agents.manager.analyst.get_llm_client", return_value=mock_llm):
            result = await analyst(state)
            # LLM should NOT have been called — pre-check intercepts
            mock_llm.ainvoke.assert_not_called()
            assert result["tool_to_call"] == "confirm_plan"
            assert result["phase"] == "tool"

    async def test_confirm_n_intercepted_before_llm(self):
        """When message is 'confirm 1', the LLM should NOT be called."""
        from agents.manager.analyst import analyst
        mock_llm = AsyncMock()

        state: ManagerState = {
            "user_id": "test",
            "session_id": "test-session",
            "user_message": "confirm 1",
            "reference_now": "2026-07-15T12:00:00Z",
            "reference_timezone": "UTC",
            "slots": {
                "line": {"mention": None, "canonical": "FRUITS_TEST", "resolved": True},
                "time": {"mentioned": False, "resolved": False, "no_filter": True},
                "aim": {"raw": None, "aims": [], "reorganized": False},
                "scope": {},
                "line_slots": [],
                "active_line_index": None,
                "dataset_context": {},
            },
            "line_context": {"suggested_aims": []},
            "plan": None,
            "dataset_context": None,
            "phase": "ask",
            "chat_history": [],
            "task_confirmed": False,
            "task_definition": None,
            "planner_payload": None,
            "agent_message": "",
            "error": None,
            "analyst_reasoning": None,
            "tool_to_call": None,
            "tool_result": None,
            "saved_plans": [],
            "session_goal": None,
            "analysis_proposals": [{"id": 1, "title": "Test", "aims": ["test aim"], "what_you_might_see": "", "display_number": 1}],
            "explore_phase": None,
            "explore_iteration": 0,
            "seen_proposal_titles": [],
            "session_intent": None,
            "verification_context": None,
            "reuse_alias": None,
            "scope_selection": None,
            "scope_pending": False,
            "iot_column_wishes": [],
            "session_inventory": None,
            "explore_context": None,
            "aim_exploration": None,
            "user_explore_intent": None,
            "selected_suggested_aim": None,
            "tool_call_count": 0,
            "tool_call_history": [],
            "proposal_counter": 1,
        }

        with patch("agents.manager.analyst.get_llm_client", return_value=mock_llm):
            result = await analyst(state)
            mock_llm.ainvoke.assert_not_called()
            assert result["tool_to_call"] is None
            assert result["phase"] == "ask"
            assert "Test" in result["agent_message"]

    async def test_non_confirm_message_calls_llm(self):
        """A regular message should still call the LLM."""
        from agents.manager.analyst import analyst

        mock_response = AsyncMock()
        mock_response.content = '{"reasoning": "testing", "action": "respond", "message": "hello"}'
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        state: ManagerState = {
            "user_id": "test",
            "session_id": "test-session",
            "user_message": "hello",
            "reference_now": "2026-07-15T12:00:00Z",
            "reference_timezone": "UTC",
            "slots": {
                "line": {"mention": None, "canonical": None, "resolved": False},
                "time": {"mentioned": False, "resolved": False, "no_filter": True},
                "aim": {"raw": None, "aims": [], "reorganized": False},
                "scope": {},
                "line_slots": [],
                "active_line_index": None,
                "dataset_context": {},
            },
            "line_context": None,
            "plan": None,
            "dataset_context": None,
            "phase": "extract",
            "chat_history": [],
            "task_confirmed": False,
            "task_definition": None,
            "planner_payload": None,
            "agent_message": "",
            "error": None,
            "analyst_reasoning": None,
            "tool_to_call": None,
            "tool_result": None,
            "saved_plans": [],
            "session_goal": None,
            "analysis_proposals": None,
            "explore_phase": None,
            "explore_iteration": 0,
            "seen_proposal_titles": [],
            "session_intent": None,
            "verification_context": None,
            "reuse_alias": None,
            "scope_selection": None,
            "scope_pending": False,
            "iot_column_wishes": [],
            "session_inventory": None,
            "explore_context": None,
            "aim_exploration": None,
            "user_explore_intent": None,
            "selected_suggested_aim": None,
            "tool_call_count": 0,
            "tool_call_history": [],
        }

        with patch("agents.manager.analyst.get_llm_client", return_value=mock_llm):
            result = await analyst(state)
            mock_llm.ainvoke.assert_called_once()
