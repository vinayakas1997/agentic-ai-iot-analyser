"""Column templates — save, list, delete, and match against uploaded CSV columns."""

import logging

from sqlalchemy import select, delete

from db.models import ColumnTemplate
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    return name.strip().lower()


def _jaccard(uploaded: set[str], template: set[str]) -> float:
    intersection = uploaded & template
    union = uploaded | template
    if not union:
        return 0.0
    return round(len(intersection) / len(union) * 100, 1)


async def save_template(user_id: str, template_name: str, column_definitions: list[dict]) -> dict:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(ColumnTemplate).where(
                ColumnTemplate.user_id == user_id,
                ColumnTemplate.template_name == template_name
            )
        )).scalar_one_or_none()

        if existing:
            existing.column_definitions = column_definitions
            await db.commit()
            await db.refresh(existing)
            row = existing
        else:
            row = ColumnTemplate(
                user_id=user_id,
                template_name=template_name,
                column_definitions=column_definitions,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)

        return {
            "id": row.id,
            "template_name": row.template_name,
            "column_definitions": row.column_definitions,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


async def list_templates(user_id: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(ColumnTemplate)
            .where(ColumnTemplate.user_id == user_id)
            .order_by(ColumnTemplate.created_at.desc())
        )).scalars().all()

    return [
        {
            "id": r.id,
            "template_name": r.template_name,
            "column_definitions": r.column_definitions,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def delete_template(user_id: str, template_id: int) -> None:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(ColumnTemplate).where(
                ColumnTemplate.id == template_id,
                ColumnTemplate.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not row:
            raise ValueError("template_not_found")
        await db.execute(
            delete(ColumnTemplate).where(ColumnTemplate.id == template_id)
        )
        await db.commit()


async def match_templates(user_id: str, column_names: list[str]) -> list[dict]:
    """Given a list of column names from an uploaded CSV, find the top 3
    best-matching saved templates using Jaccard similarity on normalized names."""
    uploaded_normalized = {_normalize(c) for c in column_names}
    if not uploaded_normalized:
        return []

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(ColumnTemplate).where(ColumnTemplate.user_id == user_id)
        )).scalars().all()

    scored: list[tuple[float, dict]] = []
    for r in rows:
        template_cols = r.column_definitions or []
        template_normalized = set()
        template_map: dict[str, dict] = {}
        for c in template_cols:
            key = _normalize(c.get("name", ""))
            template_normalized.add(key)
            template_map[key] = c

        pct = _jaccard(uploaded_normalized, template_normalized)
        if pct <= 0:
            continue

        # Build matched columns with applied meanings
        matched_columns = []
        for c_name in column_names:
            norm = _normalize(c_name)
            if norm in template_map:
                matched_columns.append({
                    "name": c_name,
                    "meaning": template_map[norm].get("meaning", ""),
                })

        scored.append((pct, {
            "id": r.id,
            "template_name": r.template_name,
            "match_pct": pct,
            "matched_columns": matched_columns,
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:3]]
