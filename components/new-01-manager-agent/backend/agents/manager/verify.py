"""Schema verification — mock, bus, or direct DB catalog mode."""

import asyncio
import json
import logging

from sqlalchemy import select, text

from agents.manager.config import get_schema_verify_mode
from db.models import Event, GlobalRegistry
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


async def verify_against_db(schema: dict) -> dict:
    """Verify schema by checking actual column definitions in the global_registry DB table."""
    errors: list[str] = []

    table_name = schema.get("table_name")
    if not table_name:
        errors.append("Missing table_name in schema")

    if errors:
        return {"verified": False, "errors": errors}

    try:
        async with AsyncSessionLocal() as db:
            # Look up the table in global_registry by source_config->>table
            result = await db.execute(
                select(GlobalRegistry).where(
                    GlobalRegistry.source_config["table"].as_string() == table_name,
                    GlobalRegistry.status == "active",
                )
            )
            rows = result.scalars().all()

            if not rows:
                # Try matching by dataset_name
                result = await db.execute(
                    select(GlobalRegistry).where(
                        GlobalRegistry.dataset_name == table_name,
                        GlobalRegistry.status == "active",
                    )
                )
                rows = result.scalars().all()

            if not rows:
                errors.append(f"Table '{table_name}' not found in global_registry catalog")
                return {"verified": False, "errors": errors}

            # Verify column definitions match
            schema_cols = {c.get("name") for c in schema.get("column_definitions") or [] if c.get("name")}
            if schema_cols:
                found_any = False
                for row in rows:
                    registry_cols = set()
                    cols = row.column_definitions
                    if isinstance(cols, list):
                        registry_cols = {c.get("name") for c in cols if isinstance(c, dict) and c.get("name")}
                    elif isinstance(cols, dict):
                        registry_cols = set(cols.keys())

                    if registry_cols:
                        missing = schema_cols - registry_cols
                        if not missing:
                            found_any = True
                            break
                        errors.append(f"Columns missing in registry for '{table_name}': {', '.join(sorted(missing))}")

                if not found_any and errors:
                    return {"verified": False, "errors": errors}

            if errors:
                return {"verified": False, "errors": errors}
            return {"verified": True, "errors": [], "source": "db_catalog"}

    except Exception as exc:
        logger.error("DB schema verification failed: %s", exc)
        return {"verified": False, "errors": [f"Verification error: {str(exc)[:200]}"]}


async def verify_schema(schema: dict, session_id: str, user_id: str, line_name: str) -> dict:
    mode = get_schema_verify_mode()
    if mode == "bus":
        return await _verify_via_bus(schema, session_id, user_id, line_name)
    if mode == "db":
        return await verify_against_db(schema)
    return mock_verify(schema)


async def _verify_via_bus(schema: dict, session_id: str, user_id: str, line_name: str) -> dict:
    """Phase 2: publish planner.verify_schema and poll manager.schema_verified."""
    from bus.publisher import publish

    await publish(
        topic="planner.verify_schema",
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
