"""Tests for slot/session serialization — session_store.py and runner.py slot logic."""

import json

import pytest

from agents.manager.session_store import state_to_json, state_from_json, build_ui_summary, build_schema_summary


class TestStateSerialization:
    def test_state_to_json_extracts_persisted_keys_only(self):
        state = {
            "user_message": "hello",
            "phase": "ask",
            "agent_message": "hi",
            "plan": {"aims": ["test"]},
            "analysis_proposals": [{"id": 1, "title": "P1"}],
            "tool_call_count": 5,
            "analyst_reasoning": "some reasoning",
        }
        serialized = state_to_json(state)
        # Should include persisted keys
        assert "phase" in serialized
        assert "plan" in serialized
        assert "analysis_proposals" in serialized
        # Should NOT include ephemeral / non-persisted keys
        assert "user_message" not in serialized
        assert "tool_call_count" not in serialized
        assert "analyst_reasoning" not in serialized

    def test_state_to_json_serializes_chat_history(self):
        from langchain_core.messages import HumanMessage, AIMessage

        state = {
            "chat_history": [
                HumanMessage(content="hello"),
                AIMessage(content="hi there"),
            ],
        }
        serialized = state_to_json(state)
        assert "chat_history" in serialized
        assert serialized["chat_history"] == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

    def test_state_from_json_deserializes_chat_history(self):
        data = {
            "chat_history": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
            "phase": "ask",
        }
        restored = state_from_json(data)
        from langchain_core.messages import HumanMessage, AIMessage
        assert len(restored["chat_history"]) == 2
        assert isinstance(restored["chat_history"][0], HumanMessage)
        assert isinstance(restored["chat_history"][1], AIMessage)
        assert restored["phase"] == "ask"

    def test_state_from_json_handles_none(self):
        assert state_from_json(None) is None
        assert state_from_json({}) is None  # empty dict is falsy, same as None


class TestBuildUiSummary:
    def test_extract_phase_no_actions(self):
        state = {"phase": "extract", "slots": {}}
        ui = build_ui_summary(state)
        assert ui["phase"] == "extract"
        assert ui["actions"] == []

    def test_single_proposal_shows_go_proceed(self):
        state = {
            "phase": "ask",
            "plan": {"aims": ["test aim"]},
            "analysis_proposals": [{"id": 1, "title": "P1", "aims": ["test aim"]}],
            "slots": {},
        }
        ui = build_ui_summary(state)
        assert len(ui["actions"]) == 2
        assert ui["actions"][0]["label"] == "Go — proceed"
        assert ui["actions"][0]["msg"] == "__confirm__"

    def test_multiple_proposals_shows_see_more_options(self):
        state = {
            "phase": "ask",
            "analysis_proposals": [{"id": 1}, {"id": 2}, {"id": 3}],
            "slots": {},
        }
        ui = build_ui_summary(state)
        assert len(ui["actions"]) == 1
        assert ui["actions"][0]["label"] == "See more options"

    def test_executed_flag_set_when_phase_man(self):
        state = {"phase": "man", "slots": {}}
        ui = build_ui_summary(state)
        assert ui["executed"] is True

    def test_executed_flag_false_when_not_man(self):
        for phase in ("extract", "ask", "tool", "done"):
            state = {"phase": phase, "slots": {}}
            ui = build_ui_summary(state)
            assert ui["executed"] is False, f"executed should be False for phase={phase}"

    def test_time_default_notice_shown_when_no_filter(self):
        state = {
            "phase": "ask",
            "slots": {
                "time": {"no_filter": True, "data_earliest": "2025-01-01"},
            },
        }
        ui = build_ui_summary(state)
        assert ui["time_default_notice"] is not None
        assert "all available data" in ui["time_default_notice"]


class TestBuildSchemaSummary:
    def test_returns_expected_keys(self):
        state = {
            "line_context": {"suggested_aims": []},
            "slots": {
                "line": {},
                "time": {},
            },
        }
        schema = build_schema_summary(state)
        assert "line" in schema
        assert "datasets" in schema
        assert "columns" in schema
        assert "suggested_aims" in schema

    def test_no_line_context_returns_empty(self):
        state = {"slots": {"line": {}, "time": {}}}
        schema = build_schema_summary(state)
        assert schema["datasets"] == []
        assert schema["columns"] == []
        assert schema["suggested_aims"] == []
