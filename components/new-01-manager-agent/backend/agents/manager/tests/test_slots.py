"""Tests for slot management — slots.py and slot_inventory.py."""

import pytest

from agents.manager.slots import (
    compute_missing,
    empty_line_slot,
    empty_slots,
    session_state_for_llm,
    time_needs_clarification,
)
from agents.manager.slot_inventory import (
    MultiMissing,
    build_line_slots_from_extraction,
    compute_multi_missing,
    empty_aim_exploration,
    format_slot_summary,
    match_mention_to_existing,
    normalize_mention,
    parse_aim_exploration,
    prepare_questions,
    sync_active_line,
)


class TestEmptySlots:
    def test_has_required_keys(self):
        slots = empty_slots()
        assert "line" in slots
        assert "time" in slots
        assert "aim" in slots
        assert "scope" in slots
        assert "line_slots" in slots
        assert "dataset_context" in slots

    def test_line_defaults(self):
        slots = empty_slots()
        assert slots["line"]["mention"] is None
        assert slots["line"]["resolved"] is False
        assert slots["line"]["candidates"] == []

    def test_time_defaults(self):
        slots = empty_slots()
        assert slots["time"]["raw"] is None
        assert slots["time"]["resolved"] is False
        assert slots["time"]["ambiguous"] is False

    def test_aim_defaults(self):
        slots = empty_slots()
        assert slots["aim"]["raw"] is None
        assert slots["aim"]["aims"] == []
        assert slots["aim"]["reorganized"] is False


class TestComputeMissing:
    def test_missing_line_when_not_resolved(self):
        slots = empty_slots()
        assert "line" in compute_missing(slots)

    def test_missing_aim_when_empty(self):
        slots = empty_slots()
        assert "aim" in compute_missing(slots)

    def test_no_missing_when_both_provided(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["aim"]["raw"] = "analyze sales"
        missing = compute_missing(slots)
        assert "line" not in missing
        assert "aim" not in missing

    def test_aim_not_missing_when_aims_list_present(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["aim"]["aims"] = ["analyze sales"]
        missing = compute_missing(slots)
        assert "aim" not in missing


class TestTimeNeedsClarification:
    def test_no_clarification_when_not_mentioned(self):
        slots = empty_slots()
        assert time_needs_clarification(slots) is False

    def test_needs_clarification_when_ambiguous(self):
        slots = empty_slots()
        slots["time"]["mentioned"] = True
        slots["time"]["ambiguous"] = True
        assert time_needs_clarification(slots) is True

    def test_no_clarification_when_no_filter(self):
        slots = empty_slots()
        slots["time"]["mentioned"] = True
        slots["time"]["no_filter"] = True
        assert time_needs_clarification(slots) is False

    def test_needs_clarification_when_raw_but_not_resolved(self):
        slots = empty_slots()
        slots["time"]["mentioned"] = True
        slots["time"]["raw"] = "last week"
        slots["time"]["resolved"] = False
        assert time_needs_clarification(slots) is True


class TestEmptyLineSlot:
    def test_defaults(self):
        slot = empty_line_slot()
        assert slot["mention"] == ""
        assert slot["resolved"] is False
        assert slot["status"] == "pending"
        assert slot["skipped"] is False

    def test_with_mention(self):
        slot = empty_line_slot("FRUITS_TEST")
        assert slot["mention"] == "FRUITS_TEST"


class TestMatchMentionToExisting:
    def test_exact_match(self):
        slots = [{"mention": "FRUITS_TEST"}, {"mention": "VEGGIES_TEST"}]
        assert match_mention_to_existing("FRUITS_TEST", slots) == 0
        assert match_mention_to_existing("VEGGIES_TEST", slots) == 1

    def test_case_insensitive(self):
        slots = [{"mention": "fruits_test"}]
        assert match_mention_to_existing("FRUITS_TEST", slots) == 0

    def test_no_match_returns_none(self):
        slots = [{"mention": "FRUITS_TEST"}]
        assert match_mention_to_existing("UNKNOWN", slots) is None


class TestNormalizeMention:
    def test_removes_underscores(self):
        assert normalize_mention("FRUITS_TEST") == "fruits test"

    def test_lowercases(self):
        assert normalize_mention("Fruits Test") == "fruits test"

    def test_handles_none(self):
        assert normalize_mention(None) == ""


class TestParseAimExploration:
    def test_empty_when_no_input(self):
        result = parse_aim_exploration(None)
        assert result["action"] is None

    def test_parses_action(self):
        clar = {"aim_exploration": {"action": "propose"}}
        result = parse_aim_exploration(clar)
        assert result["action"] == "propose"

    def test_parses_plan_ids(self):
        clar = {"aim_exploration": {"selected_plan_ids": [1, 2]}}
        result = parse_aim_exploration(clar)
        assert result["selected_plan_ids"] == [1, 2]

    def test_reject_plan(self):
        clar = {"aim_exploration": {"action": "reject_plan"}}
        result = parse_aim_exploration(clar)
        assert result["reject_current_plan"] is True


class TestEmptyAimExploration:
    def test_defaults(self):
        e = empty_aim_exploration()
        assert e["action"] is None
        assert e["selected_plan_ids"] == []
        assert e["reject_current_plan"] is False


class TestComputeMultiMissing:
    def test_no_line_slots_returns_no_clarification(self):
        slots = empty_slots()
        result = compute_multi_missing(slots)
        assert result.needs_any_clarification is False

    def test_ambiguous_slots_needs_clarification(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS", "status": "ambiguous", "candidates": ["FRUITS_TEST", "FRUITS_PROD"]}
        ]
        result = compute_multi_missing(slots)
        assert result.needs_any_clarification is True
        assert len(result.ambiguous_slots) == 1

    def test_not_found_with_resolved_needs_active_line_choice(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS_TEST", "status": "resolved", "canonical": "FRUITS_TEST", "skipped": False},
            {"mention": "UNKNOWN", "status": "not_found", "skipped": False},
        ]
        result = compute_multi_missing(slots)
        assert result.needs_any_clarification is True
        assert len(result.not_found_slots) == 1


class TestPrepareQuestions:
    def test_ambiguous_slot_generates_question(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS", "status": "ambiguous", "candidates": ["FRUITS_TEST", "FRUITS_PROD"]}
        ]
        missing = MultiMissing(
            ambiguous_slots=[{"mention": "FRUITS", "candidates": ["FRUITS_TEST", "FRUITS_PROD"]}]
        )
        questions = prepare_questions(slots, missing)
        assert len(questions) == 1
        assert "FRUITS" in questions[0]["text"]

    def test_missing_aim_generates_question(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS_TEST", "status": "resolved", "canonical": "FRUITS_TEST", "skipped": False}
        ]
        missing = MultiMissing(missing_aim=True)
        questions = prepare_questions(slots, missing)
        assert any("analysis" in q["text"].lower() for q in questions)


class TestFormatSlotSummary:
    def test_empty_when_no_line_slots(self):
        slots = empty_slots()
        assert format_slot_summary(slots) == ""

    def test_shows_resolved_line(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS_TEST", "status": "resolved", "canonical": "FRUITS_TEST", "skipped": False,
             "source": "line_name"}
        ]
        summary = format_slot_summary(slots)
        assert "FRUITS_TEST" in summary
        assert "1 machine" in summary


class TestSyncActiveLine:
    def test_copies_line_slot_to_line(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS_TEST", "canonical": "FRUITS_TEST", "resolved": True, "source": "line_name",
             "candidates": [], "status": "resolved", "skipped": False, "aim_raw": None, "time_raw": None,
             "lookup_locked": False}
        ]
        slots["active_line_index"] = 0
        result = sync_active_line(slots)
        assert result["line"]["canonical"] == "FRUITS_TEST"
        assert result["line"]["resolved"] is True


class TestBuildLineSlotsFromExtraction:
    def test_creates_line_slot_from_mention(self):
        slots = empty_slots()
        extracted = {"line_mentions": ["FRUITS_TEST"]}
        result = build_line_slots_from_extraction(slots, extracted)
        assert len(result.get("line_slots", [])) == 1
        assert result["line_slots"][0]["mention"] == "FRUITS_TEST"

    def test_multiple_mentions(self):
        slots = empty_slots()
        extracted = {"line_mentions": ["FRUITS_TEST", "VEGGIES_TEST"]}
        result = build_line_slots_from_extraction(slots, extracted)
        assert len(result.get("line_slots", [])) == 2

    def test_preserves_existing_lookup_locked(self):
        slots = empty_slots()
        slots["line_slots"] = [
            {"mention": "FRUITS_TEST", "status": "resolved", "canonical": "FRUITS_TEST", "lookup_locked": True,
             "skipped": False, "aim_raw": None, "time_raw": None, "source": "line_name", "candidates": []}
        ]
        extracted = {"line_mentions": []}
        result = build_line_slots_from_extraction(slots, extracted)
        # lookup_locked slot should be preserved
        assert len(result.get("line_slots", [])) >= 1


class TestSessionStateForLLM:
    def test_contains_expected_keys(self):
        slots = empty_slots()
        slots["line"]["resolved"] = True
        slots["line"]["canonical"] = "FRUITS_TEST"
        state = session_state_for_llm(slots, phase="plan", has_plan=True)
        assert "line_canonical" in state
        assert "phase" in state
        assert "has_plan" in state
        assert state["phase"] == "plan"
        assert state["has_plan"] is True
