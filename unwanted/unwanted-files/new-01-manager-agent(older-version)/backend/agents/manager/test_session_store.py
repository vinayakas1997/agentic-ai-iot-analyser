"""Unit tests for manager session state serialization."""

from langchain_core.messages import AIMessage, HumanMessage

from agents.manager.session_store import (
    build_ui_summary,
    session_status_from_state,
    state_from_json,
    state_to_json,
)
from agents.manager.slots import empty_slots


def test_state_to_json_round_trip_chat_history() -> None:
    state = {
        "phase": "plan",
        "slots": empty_slots(),
        "chat_history": [
            HumanMessage(content="Vinayaka"),
            AIMessage(content="Which aim?"),
        ],
        "user_message": "should be excluded",
        "agent_message": "ephemeral",
        "reference_now": "2026-01-01T00:00:00Z",
    }
    blob = state_to_json(state)
    assert "user_message" not in blob
    assert "agent_message" not in blob
    assert "reference_now" not in blob
    assert blob["chat_history"] == [
        {"role": "user", "content": "Vinayaka"},
        {"role": "assistant", "content": "Which aim?"},
    ]

    restored = state_from_json(blob)
    assert restored is not None
    assert len(restored["chat_history"]) == 2
    assert isinstance(restored["chat_history"][0], HumanMessage)
    assert isinstance(restored["chat_history"][1], AIMessage)
    assert restored["chat_history"][0].content == "Vinayaka"


def test_build_ui_summary_shape() -> None:
    slots = empty_slots()
    slots["line"] = {"canonical": "FRUITS_TEST", "resolved": True}
    state = {
        "phase": "plan",
        "slots": slots,
        "missing": [],
        "plan": {"aims": ["Analyze defects"]},
        "analysis_proposals": [{"id": 1}],
        "saved_plans": [],
        "scope_pending": False,
        "planner_payload": None,
    }
    ui = build_ui_summary(state)
    assert ui["phase"] == "plan"
    assert ui["line"] == "FRUITS_TEST"
    assert ui["plan"]["aims"] == ["Analyze defects"]
    assert ui["proposals"] == [{"id": 1}]
    assert ui["done"] is False


def test_session_status_completed_on_done_phase() -> None:
    assert session_status_from_state({"phase": "done"}) == "completed"
    assert session_status_from_state({"phase": "plan", "planner_payload": {"x": 1}}) == "completed"
    assert session_status_from_state({"phase": "plan"}) == "active"
