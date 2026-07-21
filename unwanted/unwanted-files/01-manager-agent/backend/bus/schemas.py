from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    task_id: UUID | None = None
    session_id: str | None = None
    parent_event_id: UUID | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    event_id: UUID
    topic: str
    user_id: str
    session_id: str | None
    payload: dict[str, Any]
    status: str
    consumed_by: str | None
    attempt: int
    execute_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
