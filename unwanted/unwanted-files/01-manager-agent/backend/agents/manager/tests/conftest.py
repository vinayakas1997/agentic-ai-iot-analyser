"""Shared test fixtures for manager agent tests."""

from typing import Any

import pytest

from agents.manager.slots import empty_slots


@pytest.fixture
def empty_state() -> dict[str, Any]:
    return {
        "user_id": "test_user",
        "session_id": "test_session",
        "user_message": "",
        "reference_now": "2026-06-19T12:00:00+00:00",
        "reference_timezone": "UTC",
        "slots": empty_slots(),
        "missing": [],
        "line_context": None,
        "plan": None,
        "phase": "extract",
        "chat_history": [],
        "task_confirmed": False,
        "task_definition": None,
        "planner_payload": None,
        "agent_message": "",
        "message_next_step": None,
        "client": "test",
        "error": None,
        "wants_suggested_aims": False,
        "analysis_proposals": None,
        "explore_phase": None,
        "aim_exploration": None,
        "explore_context": None,
        "dataset_context": None,
        "registry_sync_target": None,
        "time_context": None,
        "session_inventory": None,
        "session_intent": None,
        "verification_context": None,
        "reuse_alias": None,
        "saved_plans": None,
        "session_goal": None,
        "user_explore_intent": None,
        "scope_selection": None,
        "scope_pending": False,
        "iot_column_wishes": [],
    }


@pytest.fixture
def resolved_line_slots() -> dict:
    """State with a resolved line (FRUITS_TEST) ready for slot filling."""
    slots = empty_slots()
    slots["line"]["mention"] = "FRUITS_TEST"
    slots["line"]["canonical"] = "FRUITS_TEST"
    slots["line"]["resolved"] = True
    slots["line"]["source"] = "line_name"
    slots["line_slots"] = [
        {
            "mention": "FRUITS_TEST",
            "canonical": "FRUITS_TEST",
            "resolved": True,
            "source": "line_name",
            "candidates": [],
            "status": "resolved",
            "aim_raw": None,
            "time_raw": None,
            "skipped": False,
            "lookup_locked": False,
        }
    ]
    slots["active_line_index"] = 0
    return {"slots": slots, "line_context": {"line_name": "FRUITS_TEST", "suggested_aims": []}}


@pytest.fixture
def line_context_fruits() -> dict:
    return {
        "line_name": "FRUITS_TEST",
        "datasets": [],
        "schema": {},
        "datasets_full": [],
        "join_catalog": [],
        "dataset_summaries": [],
        "column_preview": [],
        "column_count": 0,
        "suggested_aims": [
            "Average cost by fruit type",
            "Defect rate trend over time",
            "Supplier quality comparison",
        ],
    }
