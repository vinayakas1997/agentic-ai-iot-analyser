"""Integration tests for manager session persistence (requires PostgreSQL)."""

import asyncio
import uuid
from unittest.mock import patch

from agents.manager.session_db import (
    append_chat_turn,
    create_session,
    load_chat_messages,
    load_session,
    save_session,
)
from agents.manager.session_service import get_session_detail, run_session_turn
from agents.manager.smoke_test import _mock_llm_router, _mock_resolve_time_phrase
from config import get_settings
from db.models import ChatHistory, ManagerSession
from db.session import AsyncSessionLocal
from sqlalchemy import func, select


async def test_create_load_save_session(user_id: str) -> None:
    session_id = await create_session(user_id)
    state = {
        "phase": "context",
        "slots": {"line": {"canonical": "FRUITS_TEST", "resolved": True}},
        "missing": ["aim"],
        "chat_history": [],
    }
    await save_session(user_id, session_id, state)
    loaded = await load_session(user_id, session_id)
    assert loaded is not None
    assert loaded["phase"] == "context"
    assert loaded["slots"]["line"]["canonical"] == "FRUITS_TEST"

    async with AsyncSessionLocal() as db:
        row = await db.scalar(
            select(ManagerSession).where(ManagerSession.session_id == session_id)
        )
    assert row is not None
    assert row.line_name == "FRUITS_TEST"
    assert row.phase == "context"


async def test_append_chat_turn_writes_two_rows(user_id: str) -> None:
    session_id = str(uuid.uuid4())
    await append_chat_turn(
        user_id=user_id,
        session_id=session_id,
        user_message="hello",
        agent_message="hi there",
        line_name="FRUITS_TEST",
    )
    messages = await load_chat_messages(user_id, session_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "agent"

    async with AsyncSessionLocal() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id,
            )
        )
    assert count == 2


async def test_run_session_turn_persists_state_and_chat(user_id: str) -> None:
    session_id = await create_session(user_id)
    with patch("agents.manager.nodes.extract._get_llm", _mock_llm_router):
        with patch("agents.manager.nodes.plan._get_llm", _mock_llm_router):
            with patch("agents.manager.nodes.time.resolve_time_phrase", _mock_resolve_time_phrase):
                result = await run_session_turn(
                    user_id=user_id,
                    session_id=session_id,
                    user_message="Vinayaka",
                )
    assert result["session_id"] == session_id
    assert result.get("agent_message")

    loaded = await load_session(user_id, session_id)
    assert loaded is not None
    assert loaded.get("phase")

    messages = await load_chat_messages(user_id, session_id)
    assert len(messages) >= 2

    detail = await get_session_detail(user_id, session_id)
    assert detail is not None
    assert detail["session"]["session_id"] == session_id
    assert detail["ui"]["phase"] == loaded.get("phase")


async def main() -> None:
    user_id = get_settings().default_user_id
    await test_create_load_save_session(user_id)
    await test_append_chat_turn_writes_two_rows(user_id)
    await test_run_session_turn_persists_state_and_chat(user_id)
    print("integration tests OK")


if __name__ == "__main__":
    asyncio.run(main())
