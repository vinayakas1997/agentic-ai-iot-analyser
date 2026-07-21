"""PostgreSQL persistence for manager sessions and chat_history."""

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.manager.session_store import (
    canonical_line_from_state,
    pair_messages_to_turns,
    session_status_from_state,
    state_from_json,
    state_to_json,
)
from agents.manager.names import generate_session_name
from db.models import ChatHistory, ManagerSession
from db.session import AsyncSessionLocal


async def create_session(user_id: str, title: str | None = None) -> tuple[str, str]:
    session_id = str(uuid.uuid4())
    if not title:
        title = generate_session_name()
    async with AsyncSessionLocal() as db:
        row = ManagerSession(
            session_id=session_id,
            user_id=user_id,
            phase="extract",
            status="active",
            title=title,
            state_json={"version": 1},
            version=1,
        )
        db.add(row)
        await db.commit()
    return session_id, title


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


async def save_session(user_id: str, session_id: str, state: dict, db: AsyncSession | None = None) -> None:
    phase = state.get("phase") or "extract"
    status = session_status_from_state(state)
    line_name = canonical_line_from_state(state)
    state_json = state_to_json(state)
    now = datetime.now(timezone.utc)

    async def _run(db: AsyncSession) -> None:
        result = await db.execute(
            select(ManagerSession.version).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        current_version = result.scalar_one_or_none()
        if current_version is None:
            logger.error("save_session: session %s not found for user %s", session_id, user_id)
            raise ValueError(f"Session {session_id} not found for user {user_id}")

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
                mode=phase,
                state_json=state_json,
                version=current_version + 1,
                updated_at=now,
            )
        )
        if updated.rowcount == 0:
            logger.error(
                "Concurrent session update detected for %s (version %d)",
                session_id, current_version,
            )
            raise RuntimeError(
                f"Concurrent modification detected for session {session_id}. "
                "Please retry the request."
            )
        state_json["version"] = current_version + 1

    if db is not None:
        await _run(db)
    else:
        async with AsyncSessionLocal() as db:
            await _run(db)
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
                "title": row.title,
                "mode": row.mode,
                "phase": row.phase,
                "status": row.status,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "last_message_preview": preview,
            }
        )
    return summaries


async def get_session_stats(user_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManagerSession.phase, func.count().label("count"))
            .where(ManagerSession.user_id == user_id)
            .group_by(ManagerSession.phase)
        )
        counts: dict[str, int] = {}
        for row in result:
            counts[row.phase] = row.count
    return {
        "total": sum(counts.values()),
        "phases": {
            "extract": counts.get("extract", 0),
            "ask": counts.get("ask", 0),
            "tool": counts.get("tool", 0),
            "man": counts.get("man", 0),
            "done": counts.get("done", 0),
        },
    }


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


async def update_session_title(user_id: str, session_id: str, title: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(ManagerSession)
            .where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
            .values(title=title or None)
        )
        if result.rowcount == 0:
            raise ValueError("session_not_found")
        await db.commit()


async def update_session_mode(session_id: str, user_id: str, mode: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ManagerSession)
            .where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
            .values(mode=mode, phase=mode)
        )
        await db.commit()


async def get_session_mode(session_id: str, user_id: str) -> str | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManagerSession.mode).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


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
    db: AsyncSession | None = None,
) -> int:
    async def _run(db: AsyncSession, ti: int | None) -> int:
        if ti is None:
            result = await db.execute(
                select(func.max(ChatHistory.turn_index)).where(
                    ChatHistory.user_id == user_id,
                    ChatHistory.session_id == session_id,
                )
            )
            current = result.scalar_one_or_none()
            ti = (current if current is not None else -1) + 1

        if user_message.strip():
            db.add(
                ChatHistory(
                    user_id=user_id,
                    session_id=session_id,
                    line_name=line_name,
                    role="user",
                    content=user_message.strip(),
                    node=None,
                    turn_index=ti,
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
                    turn_index=ti,
                    ui_snapshot=ui_snapshot,
                    schema_snapshot=schema_snapshot,
                )
            )
        return ti

    if db is not None:
        return await _run(db, turn_index)
    else:
        async with AsyncSessionLocal() as db:
            result = await _run(db, turn_index)
            await db.commit()
            return result
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


async def reopen_session(user_id: str, session_id: str) -> dict:
    """Reopen a done session for editing. Raises ValueError if planner already picked it up."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError("session_not_found")

        state = state_from_json(row.state_json)
        if state.get("planner_payload"):
            raise ValueError("planner_active")

        state["phase"] = "plan"
        state.pop("error", None)
        state.pop("agent_message", None)
        state_json = state_to_json(state)
        now = datetime.now(timezone.utc)

        updated = await db.execute(
            update(ManagerSession)
            .where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
                ManagerSession.version == row.version,
            )
            .values(
                phase="plan",
                status="active",
                state_json=state_json,
                version=row.version + 1,
                updated_at=now,
            )
        )
        if updated.rowcount == 0:
            raise RuntimeError(f"Concurrent modification detected for session {session_id}.")
        await db.commit()
        return {"session_id": session_id, "phase": "plan", "status": "active"}


async def fork_session(user_id: str, session_id: str) -> str:
    """Fork an existing session into a new session with copied state and chat history."""
    async with AsyncSessionLocal() as db:
        # Load existing session
        result = await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        existing_row = result.scalar_one_or_none()
        if not existing_row:
            raise ValueError("session_not_found")

        existing_state = state_from_json(existing_row.state_json)
        existing_state.pop("planner_payload", None)
        existing_state.pop("error", None)
        existing_state.pop("agent_message", None)
        existing_state.pop("task_confirmed", None)
        existing_state.pop("task_definition", None)
        existing_state["phase"] = "plan"

        # Strip completion messages from chat_history so the LLM doesn't get
        # confused seeing "Analysis plan saved and sent..." on a fresh fork
        ch = existing_state.get("chat_history")
        if ch:
            if hasattr(ch[-1], "content") and isinstance(ch[-1].content, str):
                if "saved and sent" in ch[-1].content or "execution pipeline" in ch[-1].content:
                    ch.pop()

        new_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        new_state_json = state_to_json(existing_state)
        new_state_json["version"] = 1

        # Generate derivative title
        original_title = existing_row.title or existing_row.line_name or "Session"
        suffix = " (fork)"
        candidate = f"{original_title}{suffix}"
        # Check for existing sessions with same title to avoid duplicates
        dup_result = await db.execute(
            select(ManagerSession.title).where(
                ManagerSession.user_id == user_id,
                ManagerSession.title.like(f"{original_title}{suffix}%"),
            )
        )
        existing_titles: set[str] = {t for t in dup_result.scalars().all() if t}
        if candidate in existing_titles:
            counter = 2
            while f"{original_title}{suffix} {counter}" in existing_titles:
                counter += 1
            candidate = f"{original_title}{suffix} {counter}"

        new_session = ManagerSession(
            session_id=new_id,
            user_id=user_id,
            phase="plan",
            status="active",
            mode="plan",
            line_name=existing_row.line_name,
            state_json=new_state_json,
            title=candidate,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(new_session)

        # Copy chat history
        chat_result = await db.execute(
            select(ChatHistory).where(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id,
            ).order_by(ChatHistory.created_at.asc())
        )
        for chat_row in chat_result.scalars().all():
            snapshot = dict(chat_row.ui_snapshot) if chat_row.ui_snapshot else None
            if snapshot and snapshot.get("done"):
                snapshot["done"] = False
            db.add(ChatHistory(
                user_id=user_id,
                session_id=new_id,
                line_name=chat_row.line_name,
                role=chat_row.role,
                content=chat_row.content,
                node=chat_row.node,
                turn_index=chat_row.turn_index,
                ui_snapshot=snapshot,
                schema_snapshot=chat_row.schema_snapshot,
            ))

        await db.commit()
    return new_id
