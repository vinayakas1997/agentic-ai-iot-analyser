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
from db.models import UserRegistry
from db.session import AsyncSessionLocal
from sqlite_importer import drop_user_table

logger = logging.getLogger(__name__)

_MEANING_PROMPT = """You are labeling columns of an uploaded CSV table for a data analyst.

Table: {table_name}
Columns and their first 5 sample values:
{column_samples}

For each column, write ONE short plain-English sentence describing what it likely means
(be specific about units, formats, or codes if the sample values suggest them).

Return ONLY a JSON array, no other text: [{{"name": "col_name", "meaning": "..."}}, ...]
"""


async def draft_column_meanings(table_name: str, columns: list[str], sample_rows: list[dict]) -> list[dict]:
    """LLM drafts a 1-line meaning per column from its name + first 5 sample values."""
    settings = get_settings()
    client = get_llm_client()

    lines = []
    for col in columns:
        values = [str(r.get(col)) for r in sample_rows[:5] if r.get(col) is not None]
        lines.append(f"{col}: {{{', '.join(values) if values else '(all empty)'}}}")
    prompt = _MEANING_PROMPT.format(table_name=table_name, column_samples="\n".join(lines))

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
    return [{"name": c, "meaning": by_name.get(c, "")} for c in columns]


async def create_draft_dataset(
    user_id: str,
    dataset_name: str,
    table_name: str,
    sqlite_path: str,
    original_filename: str,
    column_definitions: list[dict],
    row_count: int,
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
            "join_hints": None,
            "suggested_aims": [],
            "table": r.table_name,
            "backend": "sqlite",
            "sqlite_path": r.sqlite_path,
        }
        for r in rows
    ]


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
