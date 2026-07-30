"""Personal (user-uploaded CSV) dataset registry — drafting, confirming, listing, deleting.

Mirrors resolve.py's role for global_registry, but scoped to user_registry /
per-user SQLite files. Kept as a fully separate table so uploaded test CSVs
never touch the IoT team's global_registry.
"""

import json
import logging
import re

from sqlalchemy import select, delete

from config import get_settings, get_llm_client
from llm_client import language_instruction
from db.models import UserRegistry
from db.session import AsyncSessionLocal
from sqlite_importer import drop_user_table, user_db_path
from sqlite_executor import execute_sql

logger = logging.getLogger(__name__)

_MEANING_PROMPT = """You are labeling columns of an uploaded CSV table for a data analyst.

Table: {table_name}
Columns and their first 5 sample values:
{column_samples}

For each column, write ONE short sentence describing what it likely means
(be specific about units, formats, or codes if the sample values suggest them).
{language_instruction}
IMPORTANT: The meaning text MUST be written in the user's language shown above.
If the user's language is not English, do NOT use English for column descriptions.
Return ONLY a JSON array, no other text: [{{"name": "col_name", "meaning": "..."}}, ...]
"""


async def draft_column_meanings(
    table_name: str, columns: list[str], sample_rows: list[dict],
    display_names: list[str] | None = None,
    language: str = "en",
) -> list[dict]:
    """LLM drafts a 1-line meaning per column from its name + first 5 sample values.
    `display_names` are shown in the LLM prompt (e.g. original Japanese headers);
    `columns` are used for extracting sample values from the dicts.
    """
    if display_names is None:
        display_names = columns
    settings = get_settings()
    client = get_llm_client()

    lines = []
    for dn, col in zip(display_names, columns):
        values = [str(r.get(col)) for r in sample_rows[:5] if r.get(col) is not None]
        lines.append(f"{dn}: {{{', '.join(values) if values else '(all empty)'}}}")
    prompt = _MEANING_PROMPT.format(
        table_name=table_name, column_samples="\n".join(lines),
        language_instruction=language_instruction(language),
    )

    fallback = [{"name": c, "meaning": ""} for c in columns]
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.max_tokens,
            temperature=0.1,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("draft_column_meanings: LLM call failed")
        return fallback

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return fallback
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return fallback

    by_name = {p.get("name"): p.get("meaning", "") for p in parsed if isinstance(p, dict)}
    return [{"name": c, "meaning": by_name.get(dn, "")} for c, dn in zip(columns, display_names)]


async def create_draft_dataset(
    user_id: str,
    dataset_name: str,
    table_name: str,
    sqlite_path: str,
    original_filename: str,
    column_definitions: list[dict],
    row_count: int,
    column_profiling: dict | None = None,
) -> int:
    """Insert (or replace, on re-upload of the same dataset name) a draft user_registry row."""
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(UserRegistry).where(
                UserRegistry.user_id == user_id, UserRegistry.dataset_name == dataset_name
            )
        )).scalar_one_or_none()
        if existing:
            existing.table_name = table_name
            existing.sqlite_path = sqlite_path
            existing.original_filename = original_filename
            existing.column_definitions = column_definitions
            existing.column_profiling = column_profiling
            existing.row_count = row_count
            existing.status = "draft"
            await db.commit()
            return existing.id

        row = UserRegistry(
            user_id=user_id,
            dataset_name=dataset_name,
            table_name=table_name,
            sqlite_path=sqlite_path,
            original_filename=original_filename,
            column_definitions=column_definitions,
            column_profiling=column_profiling,
            row_count=row_count,
            status="draft",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.id


async def confirm_dataset(user_id: str, dataset_id: int, edited_columns: list[dict], description: str = "") -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(UserRegistry).where(UserRegistry.id == dataset_id, UserRegistry.user_id == user_id)
        )).scalar_one_or_none()
        if not row:
            raise ValueError("dataset_not_found")
        row.column_definitions = edited_columns
        row.status = "active"
        if description:
            row.description = description
        await db.commit()
        return {"id": row.id, "dataset_name": row.dataset_name, "status": row.status}


async def list_user_datasets(user_id: str, status: str | None = None) -> list[dict]:
    async with AsyncSessionLocal() as db:
        stmt = select(UserRegistry).where(UserRegistry.user_id == user_id)
        if status:
            stmt = stmt.where(UserRegistry.status == status)
        rows = (await db.execute(stmt.order_by(UserRegistry.created_at.desc()))).scalars().all()
    return [
        {
            "id": r.id,
            "dataset_name": r.dataset_name,
            "table_name": r.table_name,
            "original_filename": r.original_filename,
            "description": r.description,
            "column_definitions": r.column_definitions,
            "column_profiling": r.column_profiling or {},
            "row_count": r.row_count,
            "status": r.status,
        }
        for r in rows
    ]


async def fetch_active_user_datasets(user_id: str, dataset_names: list[str] | None = None) -> list[dict]:
    """Shaped like resolve.fetch_datasets(), tagged with backend='sqlite' so callers know
    which executor to use."""
    async with AsyncSessionLocal() as db:
        stmt = select(UserRegistry).where(UserRegistry.user_id == user_id, UserRegistry.status == "active")
        if dataset_names:
            stmt = stmt.where(UserRegistry.dataset_name.in_(dataset_names))
        rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "dataset_name": r.dataset_name,
            "description": r.description or f"Uploaded CSV ({r.row_count} rows)",
            "column_definitions": r.column_definitions,
            "column_profiling": r.column_profiling or {},
            "join_hints": None,
            "suggested_aims": [],
            "table": r.table_name,
            "backend": "sqlite",
            "sqlite_path": r.sqlite_path,
        }
        for r in rows
    ]


async def llm_fill_missing_meanings(user_id: str, dataset_id: int, column_names: list[str], language: str = "en") -> dict:
    """Fill empty meanings for the given columns using the LLM."""
    import sqlite3 as _sqlite3

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(UserRegistry).where(UserRegistry.id == dataset_id, UserRegistry.user_id == user_id)
        )).scalar_one_or_none()
        if not row:
            raise ValueError("dataset_not_found")

        current_defs = list(row.column_definitions)
        current_by_name = {d["name"]: d for d in current_defs}
        table_name = row.table_name
        sqlite_path = row.sqlite_path

        # Get sample rows from SQLite
        conn = _sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        try:
            cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5')
            col_names_sqlite = [d[0] for d in cursor.description]
            sample_rows = [dict(zip(col_names_sqlite, row_vals)) for row_vals in cursor.fetchall()]
        finally:
            conn.close()

        # Filter to columns that need fill and exist in the table
        columns_to_fill = [c for c in column_names if c in current_by_name and not current_by_name[c].get("meaning", "").strip()]
        if not columns_to_fill:
            return {"columns": [dict(d) for d in current_defs if d["name"] in column_names]}

        # Get display names for the columns
        display_names = [current_by_name[c].get("original_name", c) for c in columns_to_fill]

        drafted = await draft_column_meanings(table_name, columns_to_fill, sample_rows, display_names=display_names, language=language)

        by_name = {d["name"]: d["meaning"] for d in drafted}

        # Build new definitions with filled meanings
        new_defs = []
        for d in current_defs:
            entry = dict(d)
            if entry["name"] in by_name and by_name[entry["name"]].strip():
                entry["meaning"] = by_name[entry["name"]]
            new_defs.append(entry)

        row.column_definitions = new_defs
        await db.commit()
        await db.refresh(row)

    return {"columns": [d for d in new_defs if d["name"] in column_names]}


async def update_dataset_columns(user_id: str, dataset_id: int, columns: list[dict], description: str = "") -> dict:
    """Update column definitions for an existing (active) personal dataset."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(UserRegistry).where(UserRegistry.id == dataset_id, UserRegistry.user_id == user_id)
        )).scalar_one_or_none()
        if not row:
            raise ValueError("dataset_not_found")
        row.column_definitions = columns
        if description:
            row.description = description
        await db.commit()
        return {"id": row.id, "dataset_name": row.dataset_name, "status": row.status}


async def delete_user_dataset(user_id: str, dataset_id: int) -> None:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(UserRegistry).where(UserRegistry.id == dataset_id, UserRegistry.user_id == user_id)
        )).scalar_one_or_none()
        if not row:
            raise ValueError("dataset_not_found")
        table_name = row.table_name
        await db.execute(delete(UserRegistry).where(UserRegistry.id == dataset_id))
        await db.commit()
    drop_user_table(user_id, table_name)
