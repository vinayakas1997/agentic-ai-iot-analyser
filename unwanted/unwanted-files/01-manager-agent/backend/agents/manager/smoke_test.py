"""Non-interactive smoke tests for Manager Agent."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select

from agents.manager.db import resolve_line_lookup, resolve_line_name
from agents.manager.nodes.extract import set_llm
from agents.manager.runner import run_manager_agent
from agents.manager.time_resolution import apply_delta, resolve_time_phrase
from config import get_settings
from db.models import GlobalRegistry, TaskRegistry
from db.session import AsyncSessionLocal


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


def _empty_aim_exploration() -> dict:
    return {
        "action": None,
        "selected_plan_ids": [],
        "keep_plan_ids": [],
        "change_plan_ids": [],
        "change_notes": None,
        "reject_current_plan": False,
    }


def _empty_clarification() -> dict:
    return {
        "skip_mentions": [],
        "active_mention": None,
        "intent_mode": None,
        "wants_suggested_aims": False,
        "aim_exploration": _empty_aim_exploration(),
    }


def _mock_proposals(*, refined: bool = False, combine: bool = False, multi_line: bool = False) -> list[dict]:
    if combine:
        return [
            {
                "id": 1,
                "title": "Sales and quality join",
                "aims": ["Join fruits and fruit_quality on batch_id; defect rate by supplier"],
                "datasets_used": ["fruits", "fruit_quality"],
                "join_description": "batch_id",
                "what_you_might_see": "Defect patterns linked to suppliers",
                "columns_used": ["batch_id", "defect_rate", "supplier"],
            },
            {
                "id": 2,
                "title": "Grade vs sales",
                "aims": ["Join fruits and fruit_quality on batch_id; sales by quality grade"],
                "datasets_used": ["fruits", "fruit_quality"],
                "join_description": "batch_id",
                "what_you_might_see": "Revenue impact of quality grades",
                "columns_used": ["quality_grade", "total"],
            },
            {
                "id": 3,
                "title": "Storage conditions",
                "aims": ["Join fruits and fruit_quality on batch_id; defect rate by temperature"],
                "datasets_used": ["fruits", "fruit_quality"],
                "join_description": "batch_id",
                "what_you_might_see": "Temperature vs defect correlation",
                "columns_used": ["temperature_c", "defect_rate"],
            },
        ]
    third_title = "Supplier analysis" if refined else "Quality check"
    third_aim = "supplier volume by category" if refined else "count of records by status"
    lines_used = ["FRUITS_TEST", "Vinayaka"] if multi_line else ["FRUITS_TEST"]
    return [
        {
            "id": 1,
            "title": "Cost profile",
            "aims": ["average cost by fruit"],
            "what_you_might_see": "Highest and lowest cost fruits",
            "columns_used": ["cost", "fruits_name"],
            "lines_used": lines_used,
        },
        {
            "id": 2,
            "title": "Sales geography",
            "aims": ["sales by region"],
            "what_you_might_see": "Regional sales concentration",
            "columns_used": ["store_id", "quantity"],
        },
        {
            "id": 3,
            "title": third_title,
            "aims": [third_aim],
            "what_you_might_see": "Supplier and status breakdown",
            "columns_used": ["supplier", "category"],
        },
    ]


def _explore_clarification(**kwargs) -> dict:
    aim_exploration = {**_empty_aim_exploration(), **kwargs.pop("aim_exploration", {})}
    clar = _empty_clarification()
    clar["aim_exploration"] = aim_exploration
    clar.update(kwargs)
    return clar


def _extract_payload(**kwargs) -> dict:
    clarification = kwargs.pop("clarification", None)
    payload = {
        "clarification": _empty_clarification(),
        "line_mentions": [],
        "scope": {
            "intent_mode": "single",
            "joint_aim_raw": None,
            "joint_time_raw": None,
        },
        "line_slots_detail": [],
        "line_mention": None,
        "time_raw": None,
        "time_start_raw": None,
        "time_end_raw": None,
        "aim_raw": None,
    }
    if clarification is not None:
        payload["clarification"] = clarification
    payload.update(kwargs)
    return payload


async def _mock_resolve_time_phrase(phrase: str, reference_now: str, *, use_llm: bool = True):
    return await resolve_time_phrase(phrase, reference_now, use_llm=False)


def _mock_llm_router():
    async def ainvoke(messages):
        text = ""
        system_text = ""
        for m in messages:
            part = getattr(m, "content", "") or ""
            if m.__class__.__name__ == "SystemMessage" or getattr(m, "type", "") == "system":
                system_text = part.lower()
            if "User message:" in part:
                text = part.split("User message:")[-1].strip().lower()
            elif getattr(m, "type", "") == "human" or m.__class__.__name__ == "HumanMessage":
                text = part.lower()

        if "senior manufacturing data analyst advising" in system_text:
            if "business plan" in text or "next step" in text:
                return _FakeResponse(
                    "After **average cost by fruit**, run **sales by region** to see where "
                    "margin and volume align. Confirm one aim to proceed."
                )
            return _FakeResponse(
                "Average cost by fruit shows which items drive spend so you can "
                "prioritize supplier negotiations and pricing changes."
            )

        if "practical business benefits" in system_text:
            return _FakeResponse(
                "- Visibility into cost drivers\n- Supports regional pricing decisions"
            )

        if "senior data analyst" in system_text:
            refined = "action: refine" in system_text
            combine = "combine" in text or ("quality" in text and "fruit" in text)
            multi_line = "compare vinayaka" in text and "jointly" in text
            return _FakeResponse(
                json.dumps(
                    {
                        "proposals": _mock_proposals(
                            refined=refined,
                            combine=combine,
                            multi_line=multi_line,
                        )
                    }
                )
            )

        if text in ("go", "confirm", "yes", "proceed", "ok"):
            return _FakeResponse("{}")

        if "past 7 days" in text or text.strip() == "past 7 days":
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        time_raw="past 7 days",
                    )
                )
            )

        if "past two days" in text or "past 2 days" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        time_raw="past two days",
                        aim_raw="sales" if "sales" in text else None,
                    )
                )
            )

        if (
            "benefit" in text
            or "tell me more" in text
            or "new column" in text
            or "columns required" in text
            or "explain benefits" in text
            or "explain the benefits" in text
            or "business plan" in text
            or "next step" in text
        ):
            clar = _empty_clarification()
            clar["session_intent"] = "advisory"
            if "business plan" in text or "next step" in text:
                clar["wants_suggested_aims"] = True
            if "tell me more" in text:
                clar["aim_exploration"] = {
                    **_empty_aim_exploration(),
                    "action": "propose",
                }
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=clar,
                        line_mentions=["fruits test"],
                        line_mention="fruits test",
                    )
                )
            )

        if "other option" in text or "still more" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=_explore_clarification(
                            aim_exploration={"action": "propose"},
                        ),
                    )
                )
            )

        if "combine" in text and "quality" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=_explore_clarification(
                            aim_exploration={"action": "propose"},
                        ),
                        line_mentions=["fruits test"],
                        line_mention="fruits test",
                    )
                )
            )

        if "compare vinayaka" in text and "jointly" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=_explore_clarification(
                            aim_exploration={"action": "propose"},
                            intent_mode="joint",
                        ),
                        scope={
                            "intent_mode": "joint",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_mentions=["Vinayaka", "fruits test"],
                        line_slots_detail=[
                            {"mention": "Vinayaka", "aim_raw": None, "time_raw": None},
                            {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="Vinayaka",
                    )
                )
            )

        if "fruit_quality" in text or "quality table" in text:
            clar = _empty_clarification()
            clar["dataset_mentions"] = ["fruit_quality"]
            clar["include_datasets"] = ["fruit_quality"]
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=clar,
                        line_mentions=["Vinayaka"],
                        line_mention="Vinayaka",
                    )
                )
            )

        if "keep 1 and 2" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=_explore_clarification(
                            aim_exploration={
                                "action": "refine",
                                "keep_plan_ids": [1, 2],
                                "change_plan_ids": [3],
                                "change_notes": "focus on suppliers",
                            }
                        ),
                    )
                )
            )

        if "use plan 1 and 2" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=_explore_clarification(
                            aim_exploration={
                                "action": "confirm",
                                "selected_plan_ids": [1, 2],
                            }
                        ),
                    )
                )
            )

        if text.strip() == "nope":
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=_explore_clarification(
                            aim_exploration={"reject_current_plan": True}
                        ),
                    )
                )
            )

        if "status" in text and "other" not in text and "keep" not in text and "use plan" not in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        line_mentions=["fruits test"],
                        line_slots_detail=[
                            {"mention": "fruits test", "aim_raw": "status", "time_raw": None}
                        ],
                        line_mention="fruits test",
                        aim_raw="status",
                    )
                )
            )

        if "vinayaka" in text and "am307a" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification={
                            "skip_mentions": [],
                            "active_mention": None,
                            "intent_mode": "unclear",
                            "wants_suggested_aims": False,
                        },
                        line_mentions=["Vinayaka", "AM307A"],
                        scope={
                            "intent_mode": "unclear",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "Vinayaka", "aim_raw": None, "time_raw": None},
                            {"mention": "AM307A", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="Vinayaka",
                    )
                )
            )

        if "maybe we should pick one" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification={},
                        line_mentions=["Am307A", "fruits test"],
                        scope={
                            "intent_mode": "unclear",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "Am307A", "aim_raw": None, "time_raw": None},
                            {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="Am307A",
                    )
                )
            )

        if ("fruits test" in text or "fruits_text" in text) and "am307" in text:
            if "forget" in text:
                return _FakeResponse(
                    json.dumps(
                        _extract_payload(
                            clarification={
                                "skip_mentions": ["AM307A"],
                                "active_mention": "fruits test",
                                "intent_mode": "single",
                                "wants_suggested_aims": "aims" in text,
                            },
                            line_mentions=["Am307A", "fruits test"],
                            scope={
                                "intent_mode": "single",
                                "joint_aim_raw": None,
                                "joint_time_raw": None,
                            },
                            line_slots_detail=[
                                {"mention": "Am307A", "aim_raw": None, "time_raw": None},
                                {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                            ],
                            line_mention="fruits test",
                        )
                    )
                )
            if "don't use" in text or "dont use" in text:
                return _FakeResponse(
                    json.dumps(
                        _extract_payload(
                            clarification={
                                "skip_mentions": ["AM307A"],
                                "active_mention": "fruits test",
                                "intent_mode": "single",
                                "wants_suggested_aims": False,
                            },
                            line_mentions=["Am307A", "fruits test"],
                            scope={
                                "intent_mode": "single",
                                "joint_aim_raw": None,
                                "joint_time_raw": None,
                            },
                            line_slots_detail=[
                                {"mention": "Am307A", "aim_raw": None, "time_raw": None},
                                {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                            ],
                            line_mention="fruits test",
                        )
                    )
                )
            if "maybe" in text:
                return _FakeResponse(
                    json.dumps(
                        _extract_payload(
                            clarification={},
                            line_mentions=["Am307A", "fruits test"],
                            scope={
                                "intent_mode": "unclear",
                                "joint_aim_raw": None,
                                "joint_time_raw": None,
                            },
                            line_slots_detail=[
                                {"mention": "Am307A", "aim_raw": None, "time_raw": None},
                                {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                            ],
                            line_mention="Am307A",
                        )
                    )
                )
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        line_mentions=["Am307A", "fruits test"],
                        scope={
                            "intent_mode": "unclear",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "Am307A", "aim_raw": None, "time_raw": None},
                            {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="Am307A",
                    )
                )
            )

        if "leave" in text and ("am307" in text or "fruits" in text):
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification={},
                        line_mentions=["fruits test"],
                        scope={
                            "intent_mode": "single",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="fruits test",
                    )
                )
            )

        if "what tables" in text or "tables loaded" in text:
            clar = _empty_clarification()
            clar["session_intent"] = "meta_question"
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=clar,
                        line_mentions=["Vinayaka"],
                        line_mention="Vinayaka",
                    )
                )
            )

        if "what's still missing" in text or "what is still missing" in text:
            clar = _empty_clarification()
            clar["session_intent"] = "meta_question"
            return _FakeResponse(json.dumps(_extract_payload(clarification=clar)))

        if "is time required" in text:
            clar = _empty_clarification()
            clar["session_intent"] = "meta_question"
            return _FakeResponse(json.dumps(_extract_payload(clarification=clar)))

        if "what were the options" in text or "what were the 3 options" in text:
            clar = _empty_clarification()
            clar["session_intent"] = "meta_question"
            return _FakeResponse(json.dumps(_extract_payload(clarification=clar)))

        if "comparing both" in text or "both machines" in text:
            clar = _empty_clarification()
            clar["session_intent"] = "meta_question"
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=clar,
                        line_mentions=["Vinayaka", "fruits test"],
                        line_mention="Vinayaka",
                    )
                )
            )

        if "same as last" in text or "reuse_alias" in text:
            clar = _empty_clarification()
            clar["reuse_alias"] = "fruit cost avg"
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=clar,
                        line_mentions=["Vinayaka"],
                        line_mention="Vinayaka",
                    )
                )
            )

        if "is the data ready" in text:
            clar = _empty_clarification()
            clar["session_intent"] = "meta_question"
            return _FakeResponse(json.dumps(_extract_payload(clarification=clar)))

        if "can i join" in text:
            clar = _empty_clarification()
            clar["session_intent"] = "meta_question"
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification=clar,
                        line_mentions=["Vinayaka"],
                        line_mention="Vinayaka",
                    )
                )
            )

        if "what aims" in text or "aims we can" in text or "aims can we" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification={
                            "skip_mentions": [],
                            "active_mention": "fruits test",
                            "intent_mode": "single",
                            "wants_suggested_aims": True,
                        },
                        line_mentions=["fruits test"],
                        scope={
                            "intent_mode": "single",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="fruits test",
                    )
                )
            )

        if ("fruits test" in text or "fruits_text" in text) and "am307" not in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        line_mentions=["fruits test"],
                        scope={
                            "intent_mode": "single",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "fruits test", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="fruits test",
                    )
                )
            )

        if "continue with vinayaka" in text:
            aim_raw = "average cost by fruit" if "average cost" in text else None
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        clarification={
                            "skip_mentions": ["AM307A"],
                            "active_mention": "Vinayaka",
                            "intent_mode": "single",
                            "wants_suggested_aims": False,
                        },
                        line_mentions=["Vinayaka", "AM307A"],
                        scope={
                            "intent_mode": "single",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "Vinayaka", "aim_raw": aim_raw, "time_raw": None},
                            {"mention": "AM307A", "aim_raw": None, "time_raw": None},
                        ],
                        line_mention="Vinayaka",
                        aim_raw=aim_raw,
                    )
                )
            )

        if "vinayaka" in text and "average" not in text and "2025" not in text and "am307a" not in text:
            time_raw = None
            aim_raw = None
            if "last week" in text or ("last" in text and "week" in text):
                time_raw = "last week"
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        line_mentions=["Vinayaka"],
                        scope={
                            "intent_mode": "single",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": "Vinayaka", "aim_raw": aim_raw, "time_raw": time_raw}
                        ],
                        line_mention="Vinayaka",
                        time_raw=time_raw,
                        aim_raw=aim_raw,
                    )
                )
            )

        if "smoke_" in text:
            token = text.split()[0] if text else text
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        line_mentions=[token.upper()],
                        scope={
                            "intent_mode": "single",
                            "joint_aim_raw": None,
                            "joint_time_raw": None,
                        },
                        line_slots_detail=[
                            {"mention": token.upper(), "aim_raw": None, "time_raw": None}
                        ],
                        line_mention=token.upper(),
                    )
                )
            )

        if "average cost" in text or "2025-01-01" in text:
            return _FakeResponse(
                json.dumps(
                    _extract_payload(
                        line_mention=None,
                        time_raw="2025-01-01 to 2025-01-31",
                        aim_raw="average cost by fruit",
                    )
                )
            )

        if "reorganize" in str(messages[0].content).lower() or "datasets" in str(messages[0].content).lower():
            return _FakeResponse(
                json.dumps(
                    {
                        "aims": ["average cost by fruit"],
                        "alias_name": "fruit cost avg",
                        "notes": None,
                    }
                )
            )

        return _FakeResponse(json.dumps(_extract_payload()))

    fake = AsyncMock()
    fake.ainvoke = ainvoke
    return fake


def test_apply_delta_past_two_days() -> None:
    start, end = apply_delta("past 2 days", "2026-06-19T12:00:00+00:00")
    assert start == "2026-06-17"
    assert end == "2026-06-19"
    print("apply_delta_past_two_days OK")


async def test_resolve_line_lookup_vinayaka() -> None:
    user_id = get_settings().default_user_id
    match = await resolve_line_lookup("Vinayaka", user_id)
    assert match is not None
    assert match.canonical == "FRUITS_TEST"
    assert match.source == "synonym"
    assert await resolve_line_name("Vinayaka") == "FRUITS_TEST"
    print("resolve_line_lookup_vinayaka OK")


async def test_unknown_line_flow() -> None:
    line = f"smoke_{uuid.uuid4().hex[:8]}"
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", line)
    msg = r1.get("agent_message", "").lower()
    assert "couldn't find" in msg or "iot" in msg
    print(f"unknown_line_flow OK ({line})")


async def test_vinayaka_line_only() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "Vinayaka from last week")
    msg = r1.get("agent_message", "").lower()
    assert "unclear" in msg or "did you mean" in msg
    assert r1.get("missing") and "aim" in r1["missing"]
    assert "time" not in r1.get("missing", [])
    print("vinayaka_line_only OK")


async def test_past_two_days_resolves() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
        r2 = await run_manager_agent(
            user_id,
            session,
            "",
            "sales for past two days",
            existing_state=r1,
        )
    time_slot = (r2.get("slots") or {}).get("time") or {}
    assert time_slot.get("resolved") is True
    assert time_slot.get("start") is not None
    print("past_two_days_resolves OK")


async def test_full_flow() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
        assert r1.get("line_context") is not None

        r2 = await run_manager_agent(
            user_id,
            session,
            "",
            "average cost by fruit from 2025-01-01 to 2025-01-31",
            existing_state=r1,
        )
        assert r2.get("phase") == "plan"
        assert "plan" in r2.get("agent_message", "").lower()
        assert "all data" not in r2.get("agent_message", "").lower()

        r3 = await run_manager_agent(user_id, session, "", "go", existing_state=r2)
        assert r3.get("planner_payload") is not None
        payload = r3["planner_payload"]
        assert payload.get("line_name") == "FRUITS_TEST"
        assert payload.get("task_definition", {}).get("aims")
        assert payload.get("task_definition", {}).get("time_range") is not None
    print("full_flow OK")


async def test_multi_extract_vinayaka_am307a() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Vinayaka and the AM307A",
    )
    slots = r1.get("slots") or {}
    line_slots = slots.get("line_slots") or []
    assert len(line_slots) == 2
    assert line_slots[0].get("status") == "resolved"
    assert line_slots[0].get("canonical") == "FRUITS_TEST"
    assert line_slots[1].get("status") == "not_found"
    msg = r1.get("agent_message", "").lower()
    assert "2 machine" in msg
    assert "vinayaka" in msg
    assert "am307a" in msg
    assert "not found" in msg
    print("multi_extract_vinayaka_am307a OK")


async def test_multi_ask_not_found() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Vinayaka and the AM307A",
    )
    msg = r1.get("agent_message", "").lower()
    assert "continue with" in msg or "try another name" in msg
    assert "analysis" in msg
    print("multi_ask_not_found OK")


async def test_multi_continue_picks_active() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(
            user_id,
            session,
            "",
            "tell me about the Vinayaka and the AM307A",
        )
        r2 = await run_manager_agent(
            user_id,
            session,
            "",
            "continue with Vinayaka, show average cost by fruit",
            existing_state=r1,
        )
    slots = r2.get("slots") or {}
    assert slots.get("active_line_index") == 0
    assert slots.get("line", {}).get("canonical") == "FRUITS_TEST"
    assert r2.get("line_context") is not None
    print("multi_continue_picks_active OK")


async def test_single_line_regression() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "Vinayaka from last week")
    msg = r1.get("agent_message", "").lower()
    assert "unclear" in msg or "did you mean" in msg or "analysis" in msg
    assert r1.get("missing") and "aim" in r1["missing"]
    line_slots = (r1.get("slots") or {}).get("line_slots") or []
    assert len(line_slots) == 1
    assert line_slots[0].get("canonical") == "FRUITS_TEST"
    assert line_slots[0].get("lookup_locked") is True
    print("single_line_regression OK")


async def test_chat_history_populated() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
    assert len(r1.get("chat_history") or []) >= 2
    print("chat_history_populated OK")


async def test_followup_preserves_locked_slot() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())
    lookup_calls = []

    async def counting_lookup(mention, user_id=""):
        lookup_calls.append(mention)
        return await resolve_line_lookup(mention, user_id)

    with patch("agents.manager.nodes.multi_line.resolve_line_lookup", side_effect=counting_lookup):
        r1 = await run_manager_agent(
            user_id,
            session,
            "",
            "tell me about the Am307A and the fruits test",
        )
        slots1 = r1.get("slots") or {}
        fruits_slot = next(
            s for s in slots1.get("line_slots", []) if (s.get("mention") or "").lower() == "fruits test"
        )
        assert fruits_slot.get("lookup_locked") is True
        assert fruits_slot.get("canonical") == "FRUITS_TEST"
        calls_after_turn1 = len(lookup_calls)

        r2 = await run_manager_agent(
            user_id,
            session,
            "",
            "leave the AM307A and tell me the aims for fruits_text",
            existing_state=r1,
        )
    slots2 = r2.get("slots") or {}
    fruits2 = next(
        (s for s in slots2.get("line_slots", []) if s.get("canonical") == "FRUITS_TEST"),
        None,
    )
    assert fruits2 is not None
    assert fruits2.get("lookup_locked") is True
    assert len(lookup_calls) == calls_after_turn1
    print("followup_preserves_locked_slot OK")


async def test_leave_skips_not_found() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Am307A and the fruits test",
    )
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "leave the AM307A, continue with fruits test",
        existing_state=r1,
    )
    slots = r2.get("slots") or {}
    am_slot = next(
        (s for s in slots.get("line_slots", []) if "am307" in (s.get("mention") or "").lower()),
        None,
    )
    assert am_slot is not None
    assert am_slot.get("skipped") is True
    assert slots.get("active_line_index") is not None
    assert slots.get("line", {}).get("canonical") == "FRUITS_TEST"
    print("leave_skips_not_found OK")


async def test_show_suggested_aims() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "what aims can we do",
        existing_state=r1,
    )
    msg = r2.get("agent_message", "").lower()
    assert r2.get("line_context") is not None
    assert "suggested" in msg or "aim" in msg or "fruits_test" in msg
    print("show_suggested_aims OK")


async def test_llm_clarification_skip() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Am307A and the fruits test",
    )
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "don't use AM307A anymore, fruits test only",
        existing_state=r1,
    )
    slots = r2.get("slots") or {}
    am_slot = next(
        (s for s in slots.get("line_slots", []) if "am307" in (s.get("mention") or "").lower()),
        None,
    )
    assert am_slot is not None
    assert am_slot.get("skipped") is True
    assert slots.get("line", {}).get("canonical") == "FRUITS_TEST"
    print("llm_clarification_skip OK")


async def test_fallback_when_empty_clarification() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Am307A and the fruits test",
    )
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "leave the AM307A, continue with fruits test",
        existing_state=r1,
    )
    slots = r2.get("slots") or {}
    am_slot = next(
        (s for s in slots.get("line_slots", []) if "am307" in (s.get("mention") or "").lower()),
        None,
    )
    assert am_slot is not None
    assert am_slot.get("skipped") is True
    assert slots.get("line", {}).get("canonical") == "FRUITS_TEST"
    print("fallback_when_empty_clarification OK")


async def test_semantic_skip_forget() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Am307A and the fruits test",
    )
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "forget about AM307A, show aims for fruits test",
        existing_state=r1,
    )
    slots = r2.get("slots") or {}
    am_slot = next(
        (s for s in slots.get("line_slots", []) if "am307" in (s.get("mention") or "").lower()),
        None,
    )
    assert am_slot is not None
    assert am_slot.get("skipped") is True
    assert slots.get("line", {}).get("canonical") == "FRUITS_TEST"
    print("semantic_skip_forget OK")


async def test_still_asks_when_ambiguous() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Am307A and the fruits test",
    )
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "maybe we should pick one",
        existing_state=r1,
    )
    msg = r2.get("agent_message", "").lower()
    assert "continue with" in msg or "try another name" in msg or "analysis" in msg
    slots = r2.get("slots") or {}
    am_slot = next(
        (s for s in slots.get("line_slots", []) if "am307" in (s.get("mention") or "").lower()),
        None,
    )
    assert am_slot is not None
    assert am_slot.get("skipped") is not True
    print("still_asks_when_ambiguous OK")


def test_normalize_proposals_string_aims() -> None:
    from agents.manager.nodes.explore_aims import _normalize_proposals, format_proposals_message

    raw = [{"id": 1, "title": "Cost cut", "aims": "Identify high-cost fruits"}]
    proposals = _normalize_proposals(raw)
    assert proposals[0]["aims"] == ["Identify high-cost fruits"]

    msg = format_proposals_message(proposals, "FRUITS_TEST")
    assert "Identify high-cost fruits" in msg
    assert "I; d; e" not in msg
    print("normalize_proposals_string_aims OK")


def test_ask_missing_hints() -> None:
    from agents.manager.prompt_hints import format_ask_for_missing

    both = format_ask_for_missing(["line", "aim"])
    assert "AM307A" in both and "ZF228" in both
    assert "what aims can we do" in both.lower()
    assert "table" not in both.lower()

    aim_only = format_ask_for_missing(["aim"], {"line": {"canonical": "FRUITS_TEST", "resolved": True}})
    assert "FRUITS_TEST" in aim_only
    print("ask_missing_hints OK")


def test_explore_fallback_deeper_before_tier1() -> None:
    from agents.manager.slot_inventory import apply_clarification
    from agents.manager.slots import empty_line_slot, empty_slots

    slots = empty_slots()
    slots["line_slots"] = [empty_line_slot("fruits test")]
    slots["line_slots"][0].update(
        {"status": "resolved", "resolved": True, "canonical": "FRUITS_TEST", "lookup_locked": True}
    )
    slots["line"] = {
        "mention": "fruits test",
        "canonical": "FRUITS_TEST",
        "resolved": True,
        "source": "line_name",
        "candidates": [],
    }
    _, wants, explore, _ = apply_clarification(
        "what other deeper analysis can we do",
        slots,
        {},
    )
    assert explore.get("action") == "propose"
    assert wants is False
    print("explore_fallback_deeper_before_tier1 OK")


def test_advisory_intent_llm() -> None:
    from agents.manager.slot_inventory import parse_session_intent
    from agents.manager.slots import empty_slots

    slots = empty_slots()
    slots["line"] = {"resolved": True, "canonical": "FRUITS_TEST", "mention": "fruits_test"}
    intent = parse_session_intent(
        {"session_intent": "advisory"},
        "tell me more about category trends",
        slots,
    )
    assert intent == "advisory"
    intent_no_line = parse_session_intent(
        {"session_intent": "advisory"},
        "tell me more about category trends",
        empty_slots(),
    )
    assert intent_no_line == "fill_slots"
    print("advisory_intent_llm OK")


def test_classify_advisory_followup_business_plan() -> None:
    from agents.manager.slot_inventory import classify_advisory_followup

    assert classify_advisory_followup("what should be next business plan on fruits") is True
    assert classify_advisory_followup("what should we do next on fruits") is True
    print("classify_advisory_followup_business_plan OK")


def test_classify_advisory_followup_not_tier1() -> None:
    from agents.manager.slot_inventory import classify_advisory_followup

    assert classify_advisory_followup("what aims can we do") is False
    assert classify_advisory_followup("suggest some analysis methods") is False
    assert classify_advisory_followup("what analysis can we do") is False
    print("classify_advisory_followup_not_tier1 OK")


def test_parse_session_intent_advisory_fallback() -> None:
    from agents.manager.slot_inventory import parse_session_intent
    from agents.manager.slots import empty_slots

    slots = empty_slots()
    slots["line"] = {"resolved": True, "canonical": "FRUITS_TEST", "mention": "fruits_test"}
    intent = parse_session_intent(
        {"wants_suggested_aims": True},
        "what should be the next business plan on the fruits?",
        slots,
    )
    assert intent == "advisory"
    print("parse_session_intent_advisory_fallback OK")


def test_clarification_not_empty_for_advisory() -> None:
    from agents.manager.slot_inventory import clarification_is_empty

    assert clarification_is_empty({}) is True
    assert clarification_is_empty({"session_intent": "advisory"}) is False
    print("clarification_not_empty_for_advisory OK")


def test_advisory_clears_explore_action() -> None:
    from agents.manager.slot_inventory import apply_clarification_from_llm
    from agents.manager.slots import empty_slots

    clar = {
        "session_intent": "advisory",
        "wants_suggested_aims": True,
        "aim_exploration": {
            "action": "propose",
            "selected_plan_ids": [],
            "keep_plan_ids": [],
            "change_plan_ids": [],
            "change_notes": None,
            "reject_current_plan": False,
        },
    }
    _, wants, explore = apply_clarification_from_llm(empty_slots(), clar)
    assert explore.get("action") is None
    assert wants is False
    print("advisory_clears_explore_action OK")


def test_advisory_footer_with_plan() -> None:
    from agents.manager.prompt_hints import format_advisory_footer

    assert "go" in format_advisory_footer({"aims": ["sales by region"]}, "FRUITS_TEST").lower()
    footer = format_advisory_footer(None, "FRUITS_TEST")
    assert "what aims can we do" in footer.lower()
    print("advisory_footer_with_plan OK")


def test_scope_menu_multi_line() -> None:
    from agents.manager.scope_selection import format_scope_menu
    from agents.manager.slots import empty_line_slot, empty_slots

    slots = empty_slots()
    slots["line_slots"] = [
        {**empty_line_slot("a"), "status": "resolved", "canonical": "LINE_A", "resolved": True},
        {**empty_line_slot("b"), "status": "resolved", "canonical": "LINE_B", "resolved": True},
    ]
    msg = format_scope_menu(slots)
    assert "**1.** All machines" in msg
    assert "LINE_A" in msg
    print("scope_menu_multi_line OK")


def test_save_plan_to_shortlist_unit() -> None:
    from agents.manager.plan_library import append_saved_plan, proposal_to_saved_card

    proposals = [{"id": 1, "title": "A", "aims": ["sales"]}, {"id": 2, "title": "B", "aims": ["cost"]}]
    saved, err = append_saved_plan([], proposal_to_saved_card(proposals[1]))
    assert not err
    assert len(saved) == 1
    assert saved[0]["id"] == "S1"
    print("save_plan_to_shortlist_unit OK")


async def test_save_plan_integration() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    with patch("agents.manager.nodes.extract._get_llm", _mock_llm_router):
        with patch("agents.manager.nodes.explore_aims._get_llm", _mock_llm_router):
            r2 = await run_manager_agent(
                user_id,
                session,
                "",
                "other options please",
                existing_state=r1,
            )
            r3 = await run_manager_agent(
                user_id,
                session,
                "",
                "keep plan 2",
                existing_state=r2,
            )
    assert len(r3.get("saved_plans") or []) >= 1
    print("save_plan_integration OK")


def test_combine_saved_unit() -> None:
    from agents.manager.plan_library import combine_saved_cards

    merged = combine_saved_cards(
        [
            {"title": "A", "aims": ["sales by region"], "datasets_used": ["fruits"]},
            {"title": "B", "aims": ["average cost"], "datasets_used": ["quality"]},
        ]
    )
    assert len(merged["aims"]) == 2
    print("combine_saved_unit OK")


async def test_empty_proposals_fallback() -> None:
    from agents.manager.nodes.explore_aims import propose_or_refine_plans

    async def _empty_proposals_llm(messages):
        return _FakeResponse(json.dumps({"proposals": []}))

    state = {
        "user_message": "show me other options",
        "aim_exploration": {"action": "propose"},
        "line_context": {"line_name": "FRUITS_TEST", "suggested_aims": []},
        "slots": {
            "line": {"canonical": "FRUITS_TEST", "resolved": True},
        },
        "dataset_context": {},
        "analysis_proposals": None,
        "chat_history": [],
    }
    fake = AsyncMock()
    fake.ainvoke = _empty_proposals_llm
    with patch("agents.manager.nodes.explore_aims._get_llm", return_value=fake):
        result = await propose_or_refine_plans(state)
    assert result.get("analysis_proposals") is None
    msg = (result.get("agent_message") or "").lower()
    assert "couldn't generate" in msg
    assert "what aims can we do" in msg
    print("empty_proposals_fallback OK")


async def test_tell_me_more_routes_advisory() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me more about category trends",
        existing_state=r1,
    )
    assert r2.get("session_intent") == "advisory"
    msg = (r2.get("agent_message") or "").lower()
    assert "here are 3 analysis options" not in msg
    assert r2.get("analysis_proposals") is None
    assert "cost" in msg or "average" in msg or "spend" in msg
    print("tell_me_more_routes_advisory OK")


async def test_advisory_node_mock_llm() -> None:
    from agents.manager.nodes.advisory import answer_advisory
    from agents.manager.nodes.extract import set_llm

    set_llm(_mock_llm_router())
    state = {
        "user_message": "what benefit if I do average cost by fruit",
        "slots": {
            "line": {"resolved": True, "canonical": "FRUITS_TEST", "mention": "fruits_test"},
        },
        "line_context": {
            "line_name": "FRUITS_TEST",
            "suggested_aims": ["average cost by fruit"],
            "dataset_summaries": [{"dataset_name": "fruits", "table": "test_fruits", "role": "primary"}],
            "column_preview": [{"name": "cost", "datatype": "numeric", "meaning": "unit cost"}],
            "column_count": 1,
        },
        "dataset_context": {},
        "analysis_proposals": None,
        "plan": None,
        "explore_context": None,
    }
    result = await answer_advisory(state)
    msg = result.get("agent_message") or ""
    assert "cost" in msg.lower() or "spend" in msg.lower()
    assert "FRUITS_TEST" in msg
    assert "what aims can we do" in msg.lower()
    print("advisory_node_mock_llm OK")


async def test_show_suggested_aims_has_hints() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "what aims can we do",
        existing_state=r1,
    )
    msg = (r2.get("agent_message") or "").lower()
    assert "what aims can we do" in msg
    assert "other options" in msg
    print("show_suggested_aims_has_hints OK")


async def test_deeper_analysis_routes_to_proposals() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "what other deeper analysis can we do",
        existing_state=r1,
    )
    assert r2.get("analysis_proposals") is not None
    assert len(r2.get("analysis_proposals") or []) == 3
    assert r2.get("explore_phase") in ("proposing", "refining")
    print("deeper_analysis_routes_to_proposals OK")


async def test_advisory_after_line_resolved() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "if i do average cost by fruit what benefit would i get",
        existing_state=r1,
    )
    msg = (r2.get("agent_message") or "").lower()
    assert "still needed" not in msg
    assert "loaded tables by line" not in msg
    assert "cost" in msg or "spend" in msg
    print("advisory_after_line_resolved OK")


async def test_business_plan_routes_advisory() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "what should be the next business plan on the fruits?",
        existing_state=r1,
    )
    assert r2.get("session_intent") == "advisory"
    msg = r2.get("agent_message") or ""
    assert "**Suggested aims:**" not in msg
    assert "For **3 more analysis options**" not in msg
    assert "sales by region" in msg.lower() or "average cost" in msg.lower()
    print("business_plan_routes_advisory OK")


async def test_tier2_propose_after_more() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "what aims can we do",
        existing_state=r1,
    )
    assert "suggested" in r2.get("agent_message", "").lower()

    r3 = await run_manager_agent(
        user_id,
        session,
        "",
        "other options please",
        existing_state=r2,
    )
    msg = r3.get("agent_message", "").lower()
    assert r3.get("analysis_proposals") is not None
    assert len(r3.get("analysis_proposals") or []) == 3
    assert "analysis options" in msg or "cost profile" in msg
    assert r3.get("explore_phase") in ("proposing", "refining")
    print("tier2_propose_after_more OK")


async def test_tier2_refine_keep_1_2_change_3() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id, session, "", "what aims can we do", existing_state=r1
    )
    r3 = await run_manager_agent(
        user_id, session, "", "other options please", existing_state=r2
    )
    r4 = await run_manager_agent(
        user_id,
        session,
        "",
        "keep 1 and 2, change 3 to focus on suppliers",
        existing_state=r3,
    )
    proposals = r4.get("analysis_proposals") or []
    assert len(proposals) == 3
    plan3 = next(p for p in proposals if p.get("id") == 3)
    assert "supplier" in plan3.get("title", "").lower()
    plan1 = next(p for p in proposals if p.get("id") == 1)
    assert plan1.get("title") == "Cost profile"
    print("tier2_refine_keep_1_2_change_3 OK")


async def test_tier2_confirm_merges_to_plan() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id, session, "", "other options please", existing_state=r1
    )
    r3 = await run_manager_agent(
        user_id,
        session,
        "",
        "use plan 1 and 2",
        existing_state=r2,
    )
    assert r3.get("phase") == "plan"
    plan = r3.get("plan") or {}
    assert plan.get("aims")
    assert "average cost by fruit" in plan.get("aims", [])
    assert "sales by region" in plan.get("aims", [])
    assert "plan" in r3.get("agent_message", "").lower()
    print("tier2_confirm_merges_to_plan OK")


async def test_reject_plan_clears_stale_plan() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "fruits test")
        r2 = await run_manager_agent(
            user_id,
            session,
            "",
            "what is the status",
            existing_state=r1,
        )
    assert r2.get("plan") is not None
    r3 = await run_manager_agent(
        user_id,
        session,
        "",
        "nope",
        existing_state=r2,
    )
    assert r3.get("plan") is None
    print("reject_plan_clears_stale_plan OK")


async def test_full_schema_includes_all_datasets() -> None:
    from agents.manager.db import build_full_line_schema, fetch_global_datasets, normalize_join_catalog

    datasets = await fetch_global_datasets("FRUITS_TEST")
    schema = build_full_line_schema("FRUITS_TEST", datasets)
    assert len(schema.get("datasets") or []) >= 2
    catalog = normalize_join_catalog(datasets)
    assert any(e.get("on") == ["batch_id"] for e in catalog)
    print("full_schema_includes_all_datasets OK")


async def test_show_suggested_aims_multi_dataset() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "what aims can we do",
        existing_state=r1,
    )
    msg = r2.get("agent_message", "").lower()
    assert "fruit_quality" in msg or "known joins" in msg or "columns by dataset" in msg
    print("show_suggested_aims_multi_dataset OK")


async def test_explore_proposal_mentions_join() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "fruits test")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "combine fruits with quality table on batch_id",
        existing_state=r1,
    )
    msg = r2.get("agent_message", "").lower()
    assert "fruit_quality" in msg or "batch_id" in msg
    proposals = r2.get("analysis_proposals") or []
    assert proposals
    assert any("fruit_quality" in str(p.get("datasets_used", [])) for p in proposals)
    print("explore_proposal_mentions_join OK")


async def test_multi_line_joint_explore() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(
        user_id,
        session,
        "",
        "tell me about the Vinayaka and the fruits test",
    )
    slots = r1.get("slots") or {}
    slots["scope"] = {**(slots.get("scope") or {}), "intent_mode": "joint"}
    r1["slots"] = slots

    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "compare Vinayaka and fruits test jointly",
        existing_state=r1,
    )
    explore_ctx = r2.get("explore_context") or {}
    msg = r2.get("agent_message", "").lower()
    assert explore_ctx.get("mode") == "multi_line" or "vinayaka" in msg or "fruits_test" in msg
    assert "analysis options" in msg
    print("multi_line_joint_explore OK")


async def test_resolve_dataset_on_line() -> None:
    from agents.manager.db import fetch_global_datasets
    from agents.manager.registry_context import resolve_dataset_on_line

    datasets = await fetch_global_datasets("FRUITS_TEST")
    name = resolve_dataset_on_line("FRUITS_TEST", "quality", datasets=datasets)
    assert name == "fruit_quality"
    print("resolve_dataset_on_line OK")


async def test_exclude_dataset_filters_prompt() -> None:
    from agents.manager.db import build_full_line_schema, fetch_global_datasets
    from agents.manager.registry_context import apply_dataset_policy
    from agents.manager.schema_format import format_datasets_for_prompt

    datasets = await fetch_global_datasets("FRUITS_TEST")
    full = build_full_line_schema("FRUITS_TEST", datasets)
    filtered = apply_dataset_policy(full, ["fruits"], ["fruit_quality"], raw_datasets=datasets)
    ctx = {
        "datasets_full": filtered.get("datasets") or [],
        "join_catalog": filtered.get("join_catalog") or [],
    }
    text = format_datasets_for_prompt(ctx).lower()
    assert "fruit_quality" not in text
    assert "fruits" in text
    print("exclude_dataset_filters_prompt OK")


async def test_same_line_second_table() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
    r2 = await run_manager_agent(
        user_id,
        session,
        "",
        "what about the fruit_quality table",
        existing_state=r1,
    )
    dc = (r2.get("dataset_context") or {}).get("by_line", {}).get("FRUITS_TEST") or {}
    included = dc.get("included") or []
    assert "fruits" in included
    assert "fruit_quality" in included
    print("same_line_second_table OK")


async def test_sync_registry_context_caches() -> None:
    from agents.manager.registry_context import fetch_line_bundle, sync_dataset_context_for_state
    from agents.manager.slots import empty_slots

    calls = {"n": 0}
    real_fetch = fetch_line_bundle

    async def counting_fetch(line_name: str):
        calls["n"] += 1
        return await real_fetch(line_name)

    slots = empty_slots()
    slots["line"] = {
        "mention": "Vinayaka",
        "canonical": "FRUITS_TEST",
        "resolved": True,
        "source": "synonym",
        "candidates": [],
    }
    slots["line_slots"] = [
        {
            "mention": "Vinayaka",
            "canonical": "FRUITS_TEST",
            "resolved": True,
            "source": "synonym",
            "status": "resolved",
            "skipped": False,
            "candidates": [],
            "lookup_locked": True,
        }
    ]

    dc1, _, _, _ = await sync_dataset_context_for_state(slots, None, fetch_fn=counting_fetch)
    dc2, _, _, _ = await sync_dataset_context_for_state(slots, dc1, fetch_fn=counting_fetch)
    assert calls["n"] == 1
    assert dc2.get("by_line", {}).get("FRUITS_TEST", {}).get("loaded")
    print("sync_registry_context_caches OK")


async def test_planner_payload_in_scope() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
        r2 = await run_manager_agent(
            user_id,
            session,
            "",
            "sales for past two days",
            existing_state=r1,
        )
        r3 = await run_manager_agent(user_id, session, "", "go", existing_state=r2)

    payload = r3.get("planner_payload") or {}
    assert payload.get("datasets_in_scope")
    assert "fruits" in payload.get("datasets_in_scope", [])
    td = payload.get("task_definition") or {}
    assert td.get("datasets_in_scope")
    assert r3.get("research_payload") is None
    print("planner_payload_in_scope OK")


def test_time_inventory_resolved() -> None:
    from agents.manager.context.time import build_time_inventory

    slots = {
        "time": {
            "mentioned": True,
            "raw": "past two days",
            "resolved": True,
            "start": "2026-06-17T00:00:00+00:00",
            "end": "2026-06-19T12:00:00+00:00",
            "no_filter": False,
            "ambiguous": False,
        }
    }
    inv = build_time_inventory(slots)
    assert inv["status"] == "resolved"
    assert inv["start"]
    print("time_inventory_resolved OK")


async def test_meta_what_tables_loaded() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
        r2 = await run_manager_agent(
            user_id, session, "", "what tables are loaded", existing_state=r1
        )

    msg = (r2.get("agent_message") or "").lower()
    assert "fruits" in msg or "loaded" in msg
    assert r2.get("session_inventory")
    print("meta_what_tables_loaded OK")


async def test_meta_what_is_missing() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
        r2 = await run_manager_agent(
            user_id, session, "", "what's still missing", existing_state=r1
        )

    msg = (r2.get("agent_message") or "").lower()
    assert "missing" in msg or "aim" in msg
    print("meta_what_is_missing OK")


def test_session_inventory_in_extract_prompt() -> None:
    from agents.manager.context.session_inventory import build_session_inventory
    from agents.manager.slots import empty_slots, session_state_for_llm

    slots = empty_slots()
    slots["line"] = {"mention": "Vinayaka", "canonical": "FRUITS_TEST", "resolved": True}
    state = {
        "slots": slots,
        "phase": "context",
        "missing": ["aim"],
        "line_context": {"line_name": "FRUITS_TEST", "datasets_full": []},
    }
    state["session_inventory"] = build_session_inventory(state)
    ss = session_state_for_llm(slots, phase="context", state=state)
    assert "session_inventory" in ss
    assert ss["session_inventory"].get("registry") is not None
    print("session_inventory_in_extract_prompt OK")


async def test_meta_scope_joint() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(
            user_id, session, "", "compare Vinayaka and fruits test jointly"
        )
        r2 = await run_manager_agent(
            user_id, session, "", "are we comparing both machines", existing_state=r1
        )

    msg = (r2.get("agent_message") or "").lower()
    assert "scope" in msg or "line" in msg or "joint" in msg
    print("meta_scope_joint OK")


async def test_meta_lists_proposals() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        r1 = await run_manager_agent(user_id, session, "", "fruits test")
        r2 = await run_manager_agent(
            user_id, session, "", "show me other options", existing_state=r1
        )
        r3 = await run_manager_agent(
            user_id, session, "", "what were the 3 options", existing_state=r2
        )

    msg = r3.get("agent_message") or ""
    assert "Cost profile" in msg or "proposals" in msg.lower() or "1." in msg
    print("meta_lists_proposals OK")


async def test_task_reuse_prefill() -> None:
    session = str(uuid.uuid4())
    user_id = get_settings().default_user_id
    set_llm(_mock_llm_router())

    mock_history = [
        {
            "version": 2,
            "alias_name": "fruit cost avg",
            "aims": ["average cost by fruit"],
            "time_range": {"start": "2026-01-01", "end": "2026-01-31"},
            "datasets_in_scope": ["fruits"],
        }
    ]

    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
        with patch(
            "agents.manager.context.task_history.fetch_task_history",
            AsyncMock(return_value=mock_history),
        ):
            r1 = await run_manager_agent(user_id, session, "", "Vinayaka")
            r2 = await run_manager_agent(
                user_id, session, "", "same as last run reuse_alias", existing_state=r1
            )

    aims = (r2.get("slots") or {}).get("aim", {}).get("aims") or []
    assert "average cost by fruit" in aims or r2.get("registry_sync_target") == "reorganize"
    print("task_reuse_prefill OK")


async def test_verification_meta_not_ready() -> None:
    from agents.manager.context.meta_responses import answer_session_meta
    from agents.manager.context.session_inventory import build_session_inventory

    state = {
        "phase": "plan",
        "missing": [],
        "verification_context": {
            "verified": False,
            "checked": True,
            "errors": ["Missing required field: table_name"],
        },
        "slots": {"line": {"canonical": "FRUITS_TEST", "resolved": True}},
    }
    inv = build_session_inventory(state)
    msg = answer_session_meta("is the data ready", inv)
    assert "not ready" in msg.lower() or "missing" in msg.lower()
    print("verification_meta_not_ready OK")


def test_join_suggestion_inventory() -> None:
    from agents.manager.context.join import build_join_inventory, suggest_join_candidates

    datasets = [
        {
            "dataset_name": "fruits",
            "column_definitions": [{"name": "batch_id"}, {"name": "cost"}],
        },
        {
            "dataset_name": "fruit_quality",
            "column_definitions": [{"name": "batch_id"}, {"name": "defect_rate"}],
        },
    ]
    suggestions = suggest_join_candidates(datasets)
    assert any(s.get("on") == ["batch_id"] for s in suggestions)
    inv = build_join_inventory({"datasets_full": datasets, "join_catalog": []})
    assert inv.get("suggested_joins")
    print("join_suggestion_inventory OK")


async def test_db_counts() -> None:
    async with AsyncSessionLocal() as db:
        tasks = await db.scalar(select(func.count()).select_from(TaskRegistry))
        global_rows = await db.scalar(select(func.count()).select_from(GlobalRegistry))
    print(f"db_counts OK (task_registry={tasks}, global_registry={global_rows})")


async def main() -> None:
    test_apply_delta_past_two_days()
    test_time_inventory_resolved()
    test_session_inventory_in_extract_prompt()
    test_join_suggestion_inventory()
    test_normalize_proposals_string_aims()
    test_ask_missing_hints()
    test_explore_fallback_deeper_before_tier1()
    test_advisory_intent_llm()
    test_classify_advisory_followup_business_plan()
    test_classify_advisory_followup_not_tier1()
    test_parse_session_intent_advisory_fallback()
    test_clarification_not_empty_for_advisory()
    test_advisory_clears_explore_action()
    test_advisory_footer_with_plan()
    test_scope_menu_multi_line()
    test_save_plan_to_shortlist_unit()
    test_combine_saved_unit()
    await test_verification_meta_not_ready()
    await test_resolve_line_lookup_vinayaka()
    with patch("agents.manager.nodes.extract._get_llm", _mock_llm_router):
        with patch("agents.manager.nodes.plan._get_llm", _mock_llm_router):
            with patch("agents.manager.nodes.explore_aims._get_llm", _mock_llm_router):
                with patch("agents.manager.nodes.advisory._get_llm", _mock_llm_router):
                    with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
                        await test_advisory_node_mock_llm()
                        await test_show_suggested_aims_has_hints()
                        await test_deeper_analysis_routes_to_proposals()
                        await test_advisory_after_line_resolved()
                        await test_business_plan_routes_advisory()
                        await test_tell_me_more_routes_advisory()
                        await test_empty_proposals_fallback()
                        await test_save_plan_integration()
    with patch("agents.manager.nodes.extract._get_llm", _mock_llm_router):
        with patch("agents.manager.nodes.plan._get_llm", _mock_llm_router):
            with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
                await test_unknown_line_flow()
                await test_vinayaka_line_only()
                await test_past_two_days_resolves()
                await test_full_flow()
                await test_multi_extract_vinayaka_am307a()
                await test_multi_ask_not_found()
                await test_multi_continue_picks_active()
                await test_single_line_regression()
                await test_chat_history_populated()
                await test_followup_preserves_locked_slot()
                await test_leave_skips_not_found()
                await test_show_suggested_aims()
                await test_llm_clarification_skip()
                await test_fallback_when_empty_clarification()
                await test_semantic_skip_forget()
                await test_still_asks_when_ambiguous()
                await test_tier2_propose_after_more()
                await test_tier2_refine_keep_1_2_change_3()
                await test_tier2_confirm_merges_to_plan()
                await test_reject_plan_clears_stale_plan()
                await test_full_schema_includes_all_datasets()
                await test_show_suggested_aims_multi_dataset()
                await test_explore_proposal_mentions_join()
                await test_multi_line_joint_explore()
                await test_resolve_dataset_on_line()
                await test_exclude_dataset_filters_prompt()
                await test_same_line_second_table()
                await test_sync_registry_context_caches()
                await test_planner_payload_in_scope()
                await test_meta_what_tables_loaded()
                await test_meta_what_is_missing()
                await test_meta_scope_joint()
                await test_meta_lists_proposals()
                await test_task_reuse_prefill()
    await test_db_counts()
    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
