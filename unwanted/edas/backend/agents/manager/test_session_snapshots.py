"""Tests for Model B turn snapshots."""

import asyncio
import uuid
from unittest.mock import patch

from agents.manager.session_db import append_chat_turn, load_chat_turns, next_turn_index
from agents.manager.session_service import run_session_turn
from agents.manager.session_store import (
    build_schema_summary,
    build_turn_snapshot,
    pair_messages_to_turns,
)
from agents.manager.slots import empty_slots
from agents.manager.smoke_test import _mock_llm_router, _mock_resolve_time_phrase
from config import get_settings


def test_pair_messages_to_turns() -> None:
    rows = [
        {"turn_index": 0, "role": "user", "content": "hi", "ui_snapshot": None, "schema_snapshot": None, "created_at": "t0"},
        {
            "turn_index": 0,
            "role": "agent",
            "content": "hello",
            "ui_snapshot": {"phase": "ask"},
            "schema_snapshot": {"line": "X"},
            "created_at": "t1",
        },
        {"turn_index": 1, "role": "user", "content": "go", "ui_snapshot": None, "schema_snapshot": None, "created_at": "t2"},
        {
            "turn_index": 1,
            "role": "agent",
            "content": "ok",
            "ui_snapshot": {"phase": "done", "done": True},
            "schema_snapshot": {"line": "X"},
            "created_at": "t3",
        },
    ]
    turns = pair_messages_to_turns(rows)
    assert len(turns) == 2
    assert turns[0]["user"] == "hi"
    assert turns[0]["agent"] == "hello"
    assert turns[0]["ui"]["phase"] == "ask"
    assert turns[1]["ui"]["done"] is True


def test_build_turn_snapshot_shape() -> None:
    slots = empty_slots()
    slots["line"] = {
        "canonical": "FRUITS_TEST",
        "mention": "Vinayaka",
        "resolved": True,
        "source": "synonym",
    }
    state = {
        "phase": "plan",
        "slots": slots,
        "missing": [],
        "line_context": {
            "line_name": "FRUITS_TEST",
            "datasets_full": [],
            "suggested_aims": ["average cost by fruit"],
        },
        "dataset_context": {"by_line": {}},
        "plan": {"aims": ["test"]},
        "message_next_step": "What analysis would you like?",
    }
    snap = build_turn_snapshot(state)
    assert snap["ui"]["phase"] == "plan"
    assert snap["ui"]["line"] == "FRUITS_TEST"
    assert snap["ui"]["next_step"] == "What analysis would you like?"
    assert snap["ui"]["suggested_aims"] == ["average cost by fruit"]
    assert "columns" in snap["schema"]
    assert snap["schema"]["line"] == "FRUITS_TEST"
    assert snap["schema"]["line_match"]["canonical"] == "FRUITS_TEST"
    assert snap["schema"]["line_match"]["mention"] == "Vinayaka"
    assert snap["schema"]["suggested_aims"] == ["average cost by fruit"]


def test_assemble_reply_web_excludes_context_dump() -> None:
    from agents.manager.message_format import assemble_reply

    body = 'You said **"Vinayaka"** — matched via **synonym** to line **FRUITS_TEST**. See Context for full details.'
    context = "**Active line:** FRUITS_TEST\n\n**Context:**\n- loaded stuff"
    next_step = "What analysis would you like on **FRUITS_TEST**?"
    agent_message, message_next_step = assemble_reply(
        client="web",
        body=body,
        context_block=context,
        next_step=next_step,
    )
    assert "Active line" not in agent_message
    assert "Context:" not in agent_message
    assert agent_message == body
    assert message_next_step == next_step

    cli_message, cli_next = assemble_reply(
        client="cli",
        body=body,
        context_block=context,
        next_step=next_step,
    )
    assert "Active line" in cli_message
    assert cli_next is None


def test_format_line_match_note_skips_self_match() -> None:
    from agents.manager.message_format import format_line_match_note, format_web_body_suggested_aims

    slots = {
        "line": {
            "mention": "FRUITS_TEST",
            "canonical": "FRUITS_TEST",
            "source": "synonym",
            "resolved": True,
        }
    }
    assert format_line_match_note(slots) == ""

    body = format_web_body_suggested_aims("FRUITS_TEST")
    assert "suggested aim" in body.lower()
    assert "describe your own" in body.lower()
    assert "FRUITS_TEST" in body


async def _test_suggest_aims_web_body(user_id: str) -> None:
    from agents.manager.runner import run_manager_agent
    from agents.manager.session_db import create_session

    session_id = await create_session(user_id)
    with patch("agents.manager.nodes.extract._get_llm", _mock_llm_router):
        with patch("agents.manager.nodes.plan._get_llm", _mock_llm_router):
            with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
                r1 = await run_manager_agent(
                    user_id, session_id, "", "fruits test", client="web"
                )
                r2 = await run_manager_agent(
                    user_id,
                    session_id,
                    "",
                    "what aims can we do",
                    existing_state=r1,
                    client="web",
                )
    msg = r2.get("agent_message") or ""
    assert "Active line" not in msg
    assert "matched via" not in msg.lower()
    assert "suggested aim" in msg.lower() or "describe your own" in msg.lower()
    assert r2.get("message_next_step") or (r2.get("ui") or {}).get("next_step")


async def _test_snapshot_persisted(user_id: str) -> None:
    session_id = str(uuid.uuid4())
    turn_index = await next_turn_index(user_id, session_id)
    assert turn_index == 0

    await append_chat_turn(
        user_id=user_id,
        session_id=session_id,
        user_message="hello",
        agent_message="hi there",
        line_name="FRUITS_TEST",
        turn_index=0,
        ui_snapshot={"phase": "ask"},
        schema_snapshot={"line": "FRUITS_TEST", "columns": []},
    )
    turns = await load_chat_turns(user_id, session_id)
    assert len(turns) == 1
    assert turns[0]["ui"]["phase"] == "ask"
    assert turns[0]["schema"]["line"] == "FRUITS_TEST"


async def _test_run_session_turn_writes_snapshot(user_id: str) -> None:
    from agents.manager.session_db import create_session

    session_id = await create_session(user_id)
    with patch("agents.manager.nodes.extract._get_llm", _mock_llm_router):
        with patch("agents.manager.nodes.plan._get_llm", _mock_llm_router):
            with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
                result = await run_session_turn(
                    user_id=user_id,
                    session_id=session_id,
                    user_message="Vinayaka",
                )
    assert result.get("turn_index") == 0
    assert result.get("ui") is not None
    assert result.get("schema") is not None
    assert "Active line" not in (result.get("agent_message") or "")
    assert result.get("schema", {}).get("line_match") is not None

    turns = await load_chat_turns(user_id, session_id)
    assert len(turns) >= 1
    assert turns[-1]["ui"] is not None
    assert turns[-1]["schema"] is not None


async def main() -> None:
    test_pair_messages_to_turns()
    test_build_turn_snapshot_shape()
    test_assemble_reply_web_excludes_context_dump()
    test_format_line_match_note_skips_self_match()
    user_id = get_settings().default_user_id
    await _test_snapshot_persisted(user_id)
    await _test_run_session_turn_writes_snapshot(user_id)
    await _test_suggest_aims_web_body(user_id)
    print("snapshot tests OK")


if __name__ == "__main__":
    asyncio.run(main())
