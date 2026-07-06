"""Tests for routing.py — verify conditional edge logic for all routers."""

import pytest

from agents.manager.routing import (
    _route_explore,
    is_confirm_message,
    route_after_confirm,
    route_after_inject,
    route_after_merge,
    route_after_resolve_all_lines,
    route_after_sync_session_context,
    route_after_time,
)
from agents.manager.slots import empty_slots


def _state(**overrides) -> dict:
    state = {
        "user_message": "",
        "slots": empty_slots(),
        "phase": "extract",
        "missing": [],
        "error": None,
        "wants_suggested_aims": False,
        "aim_exploration": None,
        "analysis_proposals": None,
        "line_context": None,
        "reuse_alias": None,
        "session_intent": None,
        "registry_sync_target": None,
        "scope_pending": False,
        "scope_selection": None,
        "explore_context": None,
        "saved_plans": None,
        "explore_phase": None,
    }
    state.update(overrides)
    return state


class TestRouteAfterInject:
    def test_confirm_shortcut_when_plan_phase(self):
        s = _state(phase="plan", user_message="go")
        assert route_after_inject(s) == "detect_confirm"

    def test_confirm_shortcut_with_confirm_word(self):
        s = _state(phase="plan", user_message="yes")
        assert route_after_inject(s) == "detect_confirm"

    def test_extract_when_not_plan_phase(self):
        s = _state(phase="extract", user_message="go")
        assert route_after_inject(s) == "extract_slots"

    def test_extract_when_not_confirm_word(self):
        s = _state(phase="plan", user_message="show me options")
        assert route_after_inject(s) == "extract_slots"


class TestRouteAfterMerge:
    def test_always_goes_to_resolve(self):
        s = _state()
        assert route_after_merge(s) == "resolve_all_lines"


class TestIsConfirmMessage:
    def test_confirm_words(self):
        for word in ("go", "confirm", "yes", "proceed", "ok"):
            s = _state(phase="plan", user_message=word)
            assert is_confirm_message(s), f"'{word}' should be confirm"

    def test_not_confirm_when_not_plan_phase(self):
        s = _state(phase="ask", user_message="go")
        assert not is_confirm_message(s)

    def test_confirm_in_sentence(self):
        s = _state(phase="plan", user_message="go with this plan")
        assert is_confirm_message(s)

    def test_not_confirm_for_random_message(self):
        s = _state(phase="plan", user_message="what are the options")
        assert not is_confirm_message(s)


class TestRouteAfterResolveAllLines:
    def test_sync_session_when_line_resolved(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["line"]["canonical"] = "FRUITS_TEST"
        s = _state(slots=slots)
        result = route_after_resolve_all_lines(s)
        assert result == "sync_session_context"

    def test_ask_missing_when_no_line_or_aim(self):
        slots = empty_slots()
        s = _state(slots=slots, missing=["line", "aim"])
        result = route_after_resolve_all_lines(s)
        assert result == "ask_missing"

    def test_merge_proposals_when_explore_confirm(self):
        slots = empty_slots()
        s = _state(
            slots=slots,
            aim_exploration={"action": "confirm", "selected_plan_ids": [1, 2]},
            analysis_proposals=[{"id": 1, "title": "P1"}, {"id": 2, "title": "P2"}],
        )
        result = route_after_resolve_all_lines(s)
        assert result == "merge_proposals_to_plan"

    def test_line_not_found(self):
        slots = empty_slots()
        slots["line"]["mention"] = "unknown"
        s = _state(slots=slots, error="line_not_found")
        result = route_after_resolve_all_lines(s)
        assert result == "line_not_found"

    def test_ask_line_ambiguous(self):
        slots = empty_slots()
        slots["line"]["mention"] = "FRUITS"
        slots["line"]["candidates"] = ["FRUITS_TEST", "FRUITS_PROD"]
        s = _state(slots=slots, error="line_ambiguous")
        result = route_after_resolve_all_lines(s)
        assert result == "ask_line_ambiguous"

    def test_wants_suggested_aims(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["line"]["canonical"] = "FRUITS_TEST"
        s = _state(slots=slots, wants_suggested_aims=True, line_context={"line_name": "FRUITS_TEST"})
        result = route_after_resolve_all_lines(s)
        assert result == "show_suggested_aims"

    def test_ask_multi_missing_when_multiple_lines_unclear(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS_TEST", "status": "resolved", "canonical": "FRUITS_TEST", "skipped": False},
            {"mention": "LINE_B", "status": "resolved", "canonical": "LINE_B", "skipped": False},
        ]
        slots["scope"]["intent_mode"] = "unclear"
        s = _state(slots=slots)
        result = route_after_resolve_all_lines(s)
        assert result == "ask_multi_missing"


class TestRouteAfterSyncSessionContext:
    def test_apply_task_reuse(self):
        slots = empty_slots()
        s = _state(slots=slots, reuse_alias="last_analysis")
        result = route_after_sync_session_context(s)
        assert result == "apply_task_reuse"

    def test_answer_advisory(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["line"]["canonical"] = "FRUITS_TEST"
        s = _state(slots=slots, session_intent="advisory", line_context={"line_name": "FRUITS_TEST"})
        result = route_after_sync_session_context(s)
        assert result == "answer_advisory"

    def test_answer_session_meta(self):
        s = _state(session_intent="meta_question")
        result = route_after_sync_session_context(s)
        assert result == "answer_session_meta"

    def test_reorganize_on_registry_sync_target(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["line"]["canonical"] = "FRUITS_TEST"
        s = _state(slots=slots, registry_sync_target="reorganize", line_context={"line_name": "FRUITS_TEST"})
        result = route_after_sync_session_context(s)
        assert result == "reorganize_aim"

    def test_resolve_time_filters_when_line_context_exists(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["line"]["canonical"] = "FRUITS_TEST"
        s = _state(slots=slots, line_context={"line_name": "FRUITS_TEST"})
        result = route_after_sync_session_context(s)
        assert result == "resolve_time_filters"

    def test_end_on_no_datasets_error(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        s = _state(slots=slots, error="no_datasets")
        result = route_after_sync_session_context(s)
        assert result == "__end__"


class TestRouteAfterTime:
    def test_ask_time_ambiguous(self):
        slots = empty_slots()
        slots["time"]["ambiguous"] = True
        slots["time"]["mentioned"] = True
        s = _state(slots=slots)
        result = route_after_time(s)
        assert result == "ask_time_ambiguous"

    def test_ask_missing_when_missing_aim(self):
        slots = empty_slots()
        slots["time"]["resolved"] = True
        s = _state(slots=slots, missing=["aim"])
        result = route_after_time(s)
        assert result == "ask_missing"

    def test_sync_session_when_ready(self):
        slots = empty_slots()
        slots["time"]["resolved"] = True
        slots["line"]["resolved"] = True
        s = _state(slots=slots, missing=[])
        result = route_after_time(s)
        assert result == "sync_session_context"


class TestRouteAfterConfirm:
    def test_save_task_when_confirmed(self):
        s = _state(task_confirmed=True)
        result = route_after_confirm(s)
        assert result == "save_task_definition"

    def test_extract_when_not_confirmed(self):
        s = _state(task_confirmed=False)
        result = route_after_confirm(s)
        assert result == "extract_slots"


class TestRouteExplore:
    def test_save_action(self):
        s = _state(aim_exploration={"action": "save", "selected_plan_ids": [2]})
        result = _route_explore(s)
        assert result == "save_to_shortlist"

    def test_list_saved_action(self):
        s = _state(aim_exploration={"action": "list_saved"})
        result = _route_explore(s)
        assert result == "list_saved_plans"

    def test_activate_action(self):
        s = _state(aim_exploration={"action": "activate"})
        result = _route_explore(s)
        assert result == "activate_saved_plan"

    def test_combine_saved_action(self):
        s = _state(aim_exploration={"action": "combine_saved"})
        result = _route_explore(s)
        assert result == "combine_saved_plans"

    def test_confirm_with_proposals(self):
        s = _state(
            aim_exploration={"action": "confirm", "selected_plan_ids": [1]},
            analysis_proposals=[{"id": 1, "title": "P1"}],
        )
        result = _route_explore(s)
        assert result == "merge_proposals_to_plan"

    def test_propose_without_scope_needed(self):
        s = _state(aim_exploration={"action": "propose"})
        result = _route_explore(s)
        assert result == "propose_or_refine_plans"

    def test_no_action_returns_none(self):
        s = _state()
        result = _route_explore(s)
        assert result is None
