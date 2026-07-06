import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    consumed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    execute_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    line_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    node: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ui_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    schema_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GlobalRegistry(Base):
    __tablename__ = "global_registry"
    __table_args__ = (UniqueConstraint("line_name", "dataset_name", name="uq_global_registry_line_dataset"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_name: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_name: Mapped[str] = mapped_column(Text, nullable=False)
    synonyms: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    column_definitions: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    join_hints: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    suggested_aims: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    global_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, default="active")
    maintained_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TaskRegistry(Base):
    __tablename__ = "task_registry"
    __table_args__ = (
        UniqueConstraint("user_id", "line_name", "version", name="uq_task_registry_user_line_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    line_name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    task_definition: Mapped[dict] = mapped_column(JSONB, nullable=False)


class ManagerSession(Base):
    __tablename__ = "manager_sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False, default="extract")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    line_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
