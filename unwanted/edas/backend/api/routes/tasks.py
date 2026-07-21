import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from api.auth import get_default_user_id
from bus.publisher import publish
from db.models import Event
from db.session import AsyncSessionLocal

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    task: str
    data_source: str = "sample.csv"
    session_id: str | None = None


class TaskOut(BaseModel):
    event_id: str
    session_id: str
    task: str
    status: str


@router.post("/task")
async def create_task(body: TaskCreate) -> dict:
    user_id = get_default_user_id()
    session_id = body.session_id or str(uuid.uuid4())
    event_id = await publish(
        topic="task.new",
        user_id=user_id,
        payload={
            "data": {"task": body.task, "data_source": body.data_source},
            "session_id": session_id,
        },
        session_id=session_id,
    )
    return {"event_id": str(event_id), "session_id": session_id, "status": "pending"}


@router.get("/tasks")
async def list_tasks() -> list[TaskOut]:
    user_id = get_default_user_id()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Event)
            .where(Event.user_id == user_id, Event.topic == "task.new")
            .order_by(Event.created_at.desc())
            .limit(50)
        )
        events = result.scalars().all()

    return [
        TaskOut(
            event_id=str(e.event_id),
            session_id=e.session_id or "",
            task=e.payload.get("data", {}).get("task", ""),
            status=e.status,
        )
        for e in events
    ]
