"""Answer (report-format) templates — save, list, and delete.

Unlike column templates, these have no auto-matching: the user explicitly selects
the template they want next to the composer, and its free-text format_spec is sent
with the next message to drive the isolated template-report pipeline.
"""

import logging

from sqlalchemy import select, delete

from db.models import AnswerTemplate
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def save_answer_template(user_id: str, template_name: str, format_spec: str) -> dict:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(AnswerTemplate).where(
                AnswerTemplate.user_id == user_id,
                AnswerTemplate.template_name == template_name
            )
        )).scalar_one_or_none()

        if existing:
            existing.format_spec = format_spec
            await db.commit()
            await db.refresh(existing)
            row = existing
        else:
            row = AnswerTemplate(
                user_id=user_id,
                template_name=template_name,
                format_spec=format_spec,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)

        return {
            "id": row.id,
            "template_name": row.template_name,
            "format_spec": row.format_spec,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


async def list_answer_templates(user_id: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AnswerTemplate)
            .where(AnswerTemplate.user_id == user_id)
            .order_by(AnswerTemplate.created_at.desc())
        )).scalars().all()

    return [
        {
            "id": r.id,
            "template_name": r.template_name,
            "format_spec": r.format_spec,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


class TemplateNameConflictError(ValueError):
    pass


async def update_answer_template(user_id: str, template_id: int, template_name: str, format_spec: str) -> dict:
    """Rename and/or change the format_spec of an existing template, by id, with an
    ownership check. Raises ValueError('template_not_found') when the row is missing or
    not owned, and TemplateNameConflictError when another template already uses the
    requested name."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(AnswerTemplate).where(
                AnswerTemplate.id == template_id,
                AnswerTemplate.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not row:
            raise ValueError("template_not_found")

        conflict = (await db.execute(
            select(AnswerTemplate).where(
                AnswerTemplate.user_id == user_id,
                AnswerTemplate.template_name == template_name,
                AnswerTemplate.id != template_id,
            )
        )).scalar_one_or_none()
        if conflict:
            raise TemplateNameConflictError(template_name)

        row.template_name = template_name
        row.format_spec = format_spec
        await db.commit()
        await db.refresh(row)
        return {
            "id": row.id,
            "template_name": row.template_name,
            "format_spec": row.format_spec,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


async def delete_answer_template(user_id: str, template_id: int) -> None:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(AnswerTemplate).where(
                AnswerTemplate.id == template_id,
                AnswerTemplate.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not row:
            raise ValueError("template_not_found")
        await db.execute(
            delete(AnswerTemplate).where(AnswerTemplate.id == template_id)
        )
        await db.commit()
