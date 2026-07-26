"""IoT-team dataset registration — draft/confirm/list/delete for global_registry rows that
describe a Postgres table the IoT team's own pipeline already created and populated.

Mirrors user_datasets.py's shape, but targets GlobalRegistry (not UserRegistry) and introspects
an existing Postgres table via information_schema instead of parsing an uploaded CSV. Column
meanings are drafted with the exact same LLM helper user_datasets.py already uses — that
function takes generic (table_name, columns, sample_rows) with no CSV-specific coupling, so it's
reused unchanged here.
"""

import logging

from sqlalchemy import select, delete, text

from db.models import GlobalRegistry
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

_PG_TYPE_MAP = {
    "integer": "int", "bigint": "int", "smallint": "int",
    "double precision": "numeric", "real": "numeric", "numeric": "numeric",
    "boolean": "boolean",
    "date": "date",
    "time": "time", "time without time zone": "time", "time with time zone": "time",
    "timestamp": "date", "timestamp without time zone": "date", "timestamp with time zone": "date",
}


def _simplify_pg_type(pg_type: str) -> str:
    return _PG_TYPE_MAP.get(pg_type, "text")


class TableNotFoundError(ValueError):
    pass


async def introspect_pg_table(table_name: str) -> tuple[list[dict], list[dict]]:
    """Returns ([{name, datatype}], sample_rows) for an existing public-schema table.
    Raises TableNotFoundError if the table doesn't exist — never silently returns nothing,
    same defensive spirit as csv_validator.py's header-rejection."""
    async with AsyncSessionLocal() as db:
        exists = (await db.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"),
            {"t": table_name},
        )).scalar_one_or_none()
        if not exists:
            raise TableNotFoundError(f"Table '{table_name}' does not exist in the database.")

        col_rows = (await db.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
            ),
            {"t": table_name},
        )).all()
        columns = [{"name": r[0], "datatype": _simplify_pg_type(r[1])} for r in col_rows]

        sample = (await db.execute(text(f'SELECT * FROM "{table_name}" LIMIT 5'))).mappings().all()
        sample_rows = [dict(r) for r in sample]

    return columns, sample_rows


async def create_draft_entry(
    maintained_by: str,
    line_name: str,
    dataset_name: str,
    table_name: str,
    description: str,
    column_definitions: list[dict],
    role: str | None = None,
    join_hints: dict | list | None = None,
    suggested_aims: dict | list | None = None,
    synonyms: list[str] | None = None,
) -> int:
    """Insert (or replace, on re-registration of the same line+dataset) a draft global_registry row."""
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(GlobalRegistry).where(
                GlobalRegistry.line_name == line_name, GlobalRegistry.dataset_name == dataset_name
            )
        )).scalar_one_or_none()
        if existing:
            existing.description = description
            existing.source_type = "pg"
            existing.source_config = {"table": table_name}
            existing.column_definitions = column_definitions
            existing.role = role
            existing.join_hints = join_hints
            existing.suggested_aims = suggested_aims
            existing.synonyms = synonyms
            existing.maintained_by = maintained_by
            existing.status = "draft"
            await db.commit()
            return existing.id

        row = GlobalRegistry(
            line_name=line_name,
            dataset_name=dataset_name,
            description=description,
            source_type="pg",
            source_config={"table": table_name},
            column_definitions=column_definitions,
            role=role,
            join_hints=join_hints,
            suggested_aims=suggested_aims,
            synonyms=synonyms,
            maintained_by=maintained_by,
            status="draft",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.id


async def confirm_entry(entry_id: int, edited_columns: list[dict], description: str = "") -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(GlobalRegistry).where(GlobalRegistry.id == entry_id)
        )).scalar_one_or_none()
        if not row:
            raise ValueError("entry_not_found")
        row.column_definitions = edited_columns
        row.status = "active"
        if description:
            row.description = description
        await db.commit()
        return {"id": row.id, "dataset_name": row.dataset_name, "status": row.status}


async def list_entries(maintained_by: str | None = None) -> list[dict]:
    async with AsyncSessionLocal() as db:
        stmt = select(GlobalRegistry)
        if maintained_by:
            stmt = stmt.where(GlobalRegistry.maintained_by == maintained_by)
        rows = (await db.execute(stmt.order_by(GlobalRegistry.created_at.desc()))).scalars().all()
    return [
        {
            "id": r.id,
            "line_name": r.line_name,
            "dataset_name": r.dataset_name,
            "table": r.source_config.get("table") if r.source_config else None,
            "description": r.description,
            "column_definitions": r.column_definitions,
            "role": r.role,
            "join_hints": r.join_hints,
            "suggested_aims": r.suggested_aims,
            "synonyms": r.synonyms,
            "status": r.status,
            "maintained_by": r.maintained_by,
        }
        for r in rows
    ]


async def delete_entry(entry_id: int) -> None:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(GlobalRegistry).where(GlobalRegistry.id == entry_id)
        )).scalar_one_or_none()
        if not row:
            raise ValueError("entry_not_found")
        await db.execute(delete(GlobalRegistry).where(GlobalRegistry.id == entry_id))
        await db.commit()
