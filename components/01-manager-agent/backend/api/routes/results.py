from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from api.auth import get_default_user_id
from db.models import Result
from db.session import AsyncSessionLocal

router = APIRouter(tags=["results"])


class ResultOut(BaseModel):
    id: int
    session_id: str | None
    task: str | None
    result: dict | None
    status: str | None
    created_at: str


@router.get("/results")
async def list_results() -> list[ResultOut]:
    user_id = get_default_user_id()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Result)
            .where(Result.user_id == user_id)
            .order_by(Result.created_at.desc())
            .limit(50)
        )
        rows = result.scalars().all()

    return [
        ResultOut(
            id=r.id,
            session_id=r.session_id,
            task=r.task,
            result=r.result,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/results/{session_id}")
async def results_by_session(session_id: str) -> list[ResultOut]:
    user_id = get_default_user_id()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Result)
            .where(Result.user_id == user_id, Result.session_id == session_id)
            .order_by(Result.created_at.desc())
        )
        rows = result.scalars().all()

    return [
        ResultOut(
            id=r.id,
            session_id=r.session_id,
            task=r.task,
            result=r.result,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
