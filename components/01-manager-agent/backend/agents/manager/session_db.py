"""PostgreSQL persistence for manager sessions and chat_history."""

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from sqlalchemy import func, select, update

from agents.manager.session_store import (
    canonical_line_from_state,
    pair_messages_to_turns,
    session_status_from_state,
    state_from_json,
    state_to_json,
)
from db.models import ChatHistory, ManagerSession
from db.session import AsyncSessionLocal


async def create_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        row = ManagerSession(
            session_id=session_id,
            user_id=user_id,
            phase="extract",
            status="active",
            state_json={"version": 1},
            version=1,
        )
        db.add(row)
        await db.commit()
    return session_id


async def load_session(user_id: str, session_id: str) -> dict | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return state_from_json(row.state_json)


async def get_session_row(user_id: str, session_id: str) -> ManagerSession | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


async def save_session(user_id: str, session_id: str, state: dict) -> None:
    phase = state.get("phase") or "extract"
    status = session_status_from_state(state)
    line_name = canonical_line_from_state(state)
    state_json = state_to_json(state)
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        # Read current version from DB for optimistic locking
        result = await db.execute(
            select(ManagerSession.version).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            logger.warning("save_session: session %s not found for user %s", session_id, user_id)
            return

        current_version = row
        updated = await db.execute(
            update(ManagerSession)
            .where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
                ManagerSession.version == current_version,
            )
            .values(
                phase=phase,
                status=status,
                line_name=line_name,
                state_json=state_json,
                version=current_version + 1,
                updated_at=now,
            )
        )
        if updated.rowcount == 0:
            logger.error(
                "Concurrent session update detected for %s (version %d was %d)",
                session_id, current_version, row,
            )
            raise RuntimeError(
                f"Concurrent modification detected for session {session_id}. "
                "Please retry the request."
            )
        state_json["version"] = current_version + 1
        await db.commit()


async def list_sessions(user_id: str, limit: int = 50) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManagerSession)
            .where(ManagerSession.user_id == user_id)
            .order_by(ManagerSession.updated_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

        session_ids = [r.session_id for r in rows]

        previews: dict[str, str | None] = {}
        if session_ids:
            subq = (
                select(
                    ChatHistory.session_id,
                    ChatHistory.content,
                    func.row_number().over(
                        partition_by=ChatHistory.session_id,
                        order_by=ChatHistory.created_at.desc(),
                    ).label("rn"),
                )
                .where(
                    ChatHistory.user_id == user_id,
                    ChatHistory.session_id.in_(session_ids),
                )
                .subquery()
            )
            preview_result = await db.execute(
                select(subq.c.session_id, subq.c.content).where(subq.c.rn == 1)
            )
            for sid, content in preview_result:
                text = str(content)
                previews[sid] = text[:120] + "..." if len(text) > 120 else text

    summaries: list[dict] = []
    for row in rows:
        preview = previews.get(row.session_id)
        summaries.append(
            {
                "session_id": row.session_id,
                "line_name": row.line_name,
                "phase": row.phase,
                "status": row.status,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "last_message_preview": preview,
            }
        )
    return summaries


async def _last_message_preview(user_id: str, session_id: str) -> str | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatHistory.content)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id,
            )
            .order_by(ChatHistory.created_at.desc())
            .limit(1)
        )
        content = result.scalar_one_or_none()
    if not content:
        return None
    text = str(content)
    return text[:120] + "..." if len(text) > 120 else text


async def next_turn_index(user_id: str, session_id: str) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.max(ChatHistory.turn_index)).where(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id,
            )
        )
        current = result.scalar_one_or_none()
    return (current if current is not None else -1) + 1


async def append_chat_turn(
    user_id: str,
    session_id: str,
    user_message: str,
    agent_message: str,
    line_name: str | None = None,
    node: str | None = None,
    *,
    turn_index: int | None = None,
    ui_snapshot: dict | None = None,
    schema_snapshot: dict | None = None,
) -> int:
    if turn_index is None:
        turn_index = await next_turn_index(user_id, session_id)

    async with AsyncSessionLocal() as db:
        if user_message.strip():
            db.add(
                ChatHistory(
                    user_id=user_id,
                    session_id=session_id,
                    line_name=line_name,
                    role="user",
                    content=user_message.strip(),
                    node=None,
                    turn_index=turn_index,
                )
            )
        if agent_message.strip():
            db.add(
                ChatHistory(
                    user_id=user_id,
                    session_id=session_id,
                    line_name=line_name,
                    role="agent",
                    content=agent_message.strip(),
                    node=node,
                    turn_index=turn_index,
                    ui_snapshot=ui_snapshot,
                    schema_snapshot=schema_snapshot,
                )
            )
        await db.commit()
    return turn_index


async def load_chat_turns(user_id: str, session_id: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id,
            )
            .order_by(ChatHistory.turn_index.asc(), ChatHistory.created_at.asc())
        )
        rows = result.scalars().all()

    raw = [
        {
            "role": row.role,
            "content": row.content,
            "line_name": row.line_name,
            "node": row.node,
            "turn_index": row.turn_index,
            "ui_snapshot": row.ui_snapshot,
            "schema_snapshot": row.schema_snapshot,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return pair_messages_to_turns(raw)


async def load_chat_messages(user_id: str, session_id: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id,
            )
            .order_by(ChatHistory.created_at.asc())
        )
        rows = result.scalars().all()

    return [
        {
            "role": row.role,
            "content": row.content,
            "line_name": row.line_name,
            "node": row.node,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
