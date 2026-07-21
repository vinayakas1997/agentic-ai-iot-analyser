"""Schema verification — mock for Phase 1; bus mode stub for Phase 2."""

import asyncio
import json
import logging

from sqlalchemy import select

from agents.manager.config import get_manager_settings
from db.models import Event
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

_REQUIRED_SCHEMA_KEYS = ("source_type", "table_name", "column_definitions")
_COLUMN_KEYS = ("name", "meaning", "datatype")


def mock_verify(schema: dict) -> dict:
    """Validate schema structure locally; auto-approve if valid."""
    errors: list[str] = []

    for key in _REQUIRED_SCHEMA_KEYS:
        if key not in schema:
            errors.append(f"Missing required field: {key}")

    if schema.get("source_type") not in ("pg", "csv", None):
        errors.append("source_type must be 'pg' or 'csv'")

    columns = schema.get("column_definitions")
    if columns is not None:
        if not isinstance(columns, list) or len(columns) == 0:
            errors.append("column_definitions must be a non-empty array")
        else:
            for i, col in enumerate(columns):
                if not isinstance(col, dict):
                    errors.append(f"column_definitions[{i}] must be an object")
                    continue
                for ck in _COLUMN_KEYS:
                    if ck not in col:
                        errors.append(f"column_definitions[{i}] missing '{ck}'")

    if errors:
        return {"verified": False, "errors": errors}
    return {"verified": True, "errors": []}


async def verify_schema(schema: dict, session_id: str, user_id: str, line_name: str) -> dict:
    mode = get_manager_settings().manager_schema_verify_mode
    if mode == "bus":
        return await _verify_via_bus(schema, session_id, user_id, line_name)
    return mock_verify(schema)


async def _verify_via_bus(schema: dict, session_id: str, user_id: str, line_name: str) -> dict:
    """Phase 2: publish research.verify_schema and poll manager.schema_verified."""
    from bus.publisher import publish

    await publish(
        topic="research.verify_schema",
        user_id=user_id,
        session_id=session_id,
        payload={"line_name": line_name, "schema": schema, "session_id": session_id},
    )
    return await _poll_schema_verified(session_id)


async def _poll_schema_verified(session_id: str, timeout: int = 30) -> dict:
    for _ in range(timeout):
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Event)
                .where(
                    Event.topic == "manager.schema_verified",
                    Event.status == "done",
                )
                .order_by(Event.created_at.desc())
                .limit(20)
            )
            for row in result.scalars().all():
                payload = row.payload
                if payload.get("session_id") == session_id:
                    return payload
        await asyncio.sleep(1)
    return {"verified": False, "errors": ["Verification timeout"]}
