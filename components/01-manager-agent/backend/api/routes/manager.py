from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.manager.session_service import (
    create_session,
    fork_session_turn,
    get_session_detail,
    list_sessions,
    reopen_session_turn,
    run_session_turn,
)
from api.auth import get_default_user_id
from harness.tracer import get_trace, clear_trace

router = APIRouter(prefix="/manager", tags=["manager"])


class SessionCreateOut(BaseModel):
    session_id: str
    status: str = "active"


class MessageIn(BaseModel):
    message: str = Field(..., min_length=1)
    line_name: str = ""


@router.post("/sessions", response_model=SessionCreateOut)
async def create_manager_session() -> SessionCreateOut:
    user_id = get_default_user_id()
    session_id = await create_session(user_id)
    return SessionCreateOut(session_id=session_id)


@router.get("/sessions")
async def list_manager_sessions() -> list[dict]:
    user_id = get_default_user_id()
    return await list_sessions(user_id)


@router.get("/sessions/{session_id}")
async def get_manager_session(session_id: str) -> dict:
    user_id = get_default_user_id()
    detail = await get_session_detail(user_id, session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.post("/sessions/{session_id}/messages")
async def post_manager_message(session_id: str, body: MessageIn) -> dict:
    user_id = get_default_user_id()
    try:
        return await run_session_turn(
            user_id=user_id,
            session_id=session_id,
            user_message=body.message,
            line_name=body.line_name,
        )
    except ValueError as exc:
        if str(exc) == "session_not_found":
            raise HTTPException(status_code=404, detail="Session not found") from exc
        raise


@router.get("/sessions/{session_id}/trace")
async def get_manager_trace(session_id: str) -> list[dict]:
    return get_trace(session_id)


@router.delete("/sessions/{session_id}/trace")
async def clear_manager_trace(session_id: str) -> dict:
    clear_trace(session_id)
    return {"status": "cleared"}


@router.post("/sessions/{session_id}/reopen")
async def reopen_manager_session(session_id: str) -> dict:
    user_id = get_default_user_id()
    try:
        return await reopen_session_turn(user_id, session_id)
    except ValueError as exc:
        if str(exc) == "session_not_found":
            raise HTTPException(status_code=404, detail="Session not found") from exc
        if str(exc) == "planner_active":
            raise HTTPException(
                status_code=400,
                detail="Planner has already started processing this session.",
            ) from exc
        raise


@router.post("/sessions/{session_id}/fork")
async def fork_manager_session(session_id: str) -> dict:
    user_id = get_default_user_id()
    try:
        new_id = await fork_session_turn(user_id, session_id)
        return {"session_id": new_id}
    except ValueError as exc:
        if str(exc) == "session_not_found":
            raise HTTPException(status_code=404, detail="Session not found") from exc
        raise
