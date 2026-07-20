"""Resolve line names against global_registry with fuzzy matching."""

import re
from dataclasses import dataclass, field
from sqlalchemy import func, or_, select, text
from db.models import GlobalRegistry
from db.session import AsyncSessionLocal


@dataclass
class LineMatch:
    canonical: str
    source: str
    matched_on: str
    candidates: list[str] = field(default_factory=list)


def _normalize(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"^(a|an|the)\s+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


async def _search_by_exact(raw: str) -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GlobalRegistry.line_name)
            .where(GlobalRegistry.status == "active", func.lower(GlobalRegistry.line_name) == raw.lower())
            .distinct()
        )
        return sorted({r[0] for r in result.all()})


async def _search_by_synonym(raw: str) -> list[str]:
    async with AsyncSessionLocal() as db:
        stmt = text("""
            SELECT DISTINCT line_name FROM global_registry,
            jsonb_array_elements_text(synonyms) AS syn
            WHERE status = 'active'
            AND LOWER(syn) = LOWER(:raw)
        """)
        result = await db.execute(stmt, {"raw": raw})
        return sorted({r[0] for r in result.all()})


async def _search_fuzzy(raw: str) -> list[str]:
    norm = _normalize(raw)
    if not norm:
        return []
    async with AsyncSessionLocal() as db:
        all_lines = await db.execute(
            select(GlobalRegistry.line_name).where(GlobalRegistry.status == "active").distinct()
        )
        line_names = sorted({r[0] for r in all_lines.all()})

    scored = []
    for name in line_names:
        name_norm = _normalize(name)
        # Check substring containment
        if norm in name_norm or name_norm in norm:
            scored.append((name, 10))
            continue
        # Check character overlap
        common = len(set(norm) & set(name_norm))
        score = common / max(len(set(norm)), len(set(name_norm)), 1)
        if score >= 0.6:
            scored.append((name, score))

    scored.sort(key=lambda x: -x[1])
    return [s[0] for s in scored[:5]]


async def resolve_line_lookup(mention: str) -> LineMatch | None:
    raw = mention.strip()
    if not raw:
        return None

    candidates = await _search_by_exact(raw)
    if len(candidates) == 1:
        return LineMatch(canonical=candidates[0], source="line_name", matched_on=raw)
    if len(candidates) > 1:
        return LineMatch(canonical="", source="ambiguous", matched_on=raw, candidates=candidates)

    candidates = await _search_by_synonym(raw)
    if len(candidates) == 1:
        return LineMatch(canonical=candidates[0], source="synonym", matched_on=raw)
    if len(candidates) > 1:
        return LineMatch(canonical="", source="ambiguous", matched_on=raw, candidates=candidates)

    # Fuzzy fallback
    candidates = await _search_fuzzy(raw)
    if candidates:
        return LineMatch(canonical="", source="ambiguous", matched_on=raw, candidates=candidates)

    return None


async def fetch_datasets(line_name: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GlobalRegistry)
            .where(GlobalRegistry.line_name == line_name, GlobalRegistry.status == "active")
            .order_by(GlobalRegistry.dataset_name)
        )
        rows = result.scalars().all()
    datasets = []
    for r in rows:
        cols = r.column_definitions or []
        aims = r.suggested_aims or []
        datasets.append({
            "dataset_name": r.dataset_name,
            "description": r.description,
            "role": r.role,
            "columns": cols if isinstance(cols, list) else [],
            "suggested_aims": aims if isinstance(aims, list) else [],
            "join_hints": r.join_hints,
        })
    return datasets


async def save_task_definition(line_name: str, user_id: str, task_definition: dict) -> int:
    from db.models import TaskRegistry
    from sqlalchemy.exc import IntegrityError

    async with AsyncSessionLocal() as db:
        for attempt in range(3):
            result = await db.execute(
                select(func.coalesce(func.max(TaskRegistry.version), 0)).where(
                    TaskRegistry.user_id == user_id, TaskRegistry.line_name == line_name
                )
            )
            new_version = int(result.scalar_one()) + 1
            row = TaskRegistry(
                user_id=user_id,
                line_name=line_name,
                version=new_version,
                task_definition=task_definition,
            )
            db.add(row)
            try:
                await db.commit()
                return new_version
            except IntegrityError:
                await db.rollback()
                if attempt == 2:
                    raise
    return 0
