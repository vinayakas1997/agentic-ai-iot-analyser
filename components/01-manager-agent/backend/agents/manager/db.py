from dataclasses import dataclass, field

from sqlalchemy import func, or_, select

from db.models import GlobalRegistry, TaskRegistry
from db.session import AsyncSessionLocal


@dataclass
class LineMatch:
    canonical: str
    source: str  # line_name | synonym | task_alias | ambiguous
    matched_on: str
    candidates: list[str] = field(default_factory=list)


def _row_to_global_dict(row: GlobalRegistry) -> dict:
    cols = row.column_definitions
    return {
        "line_name": row.line_name,
        "dataset_name": row.dataset_name,
        "description": row.description,
        "source_type": row.source_type,
        "source_config": row.source_config,
        "column_definitions": cols if isinstance(cols, list) else [],
        "role": row.role,
        "join_hints": row.join_hints,
        "suggested_aims": row.suggested_aims,
        "global_version": row.global_version,
        "verified": row.verified,
    }


def _row_to_task_dict(row: TaskRegistry) -> dict:
    task_def = row.task_definition
    if isinstance(task_def, str):
        import json

        task_def = json.loads(task_def)
    return {
        "id": row.id,
        "line_name": row.line_name,
        "version": row.version,
        "task_definition": task_def,
    }


def build_schema_state(line_name: str, datasets: list[dict]) -> dict:
    """Backward-compatible primary-table schema view."""
    full = build_full_line_schema(line_name, datasets)
    primary = next((d for d in datasets if d.get("role") == "primary"), datasets[0] if datasets else {})
    return {
        "line_name": line_name,
        "source_type": primary.get("source_type"),
        "source_config": primary.get("source_config") or {},
        "column_definitions": full.get("column_definitions") or [],
        "datasets": datasets,
        "global_version": primary.get("global_version", 1),
        "datasets_full": full.get("datasets") or [],
        "join_catalog": full.get("join_catalog") or [],
    }


def _dataset_table_name(ds: dict) -> str:
    cfg = ds.get("source_config") or {}
    return str(cfg.get("table") or cfg.get("path") or "unknown")


def _dataset_full_entry(ds: dict) -> dict:
    return {
        "dataset_name": ds.get("dataset_name"),
        "table": _dataset_table_name(ds),
        "role": ds.get("role"),
        "description": ds.get("description"),
        "column_definitions": ds.get("column_definitions") or [],
        "join_hints": ds.get("join_hints"),
        "suggested_aims": list(ds.get("suggested_aims") or []),
    }


def normalize_join_catalog(datasets: list[dict]) -> list[dict]:
    """Normalize join_hints from registry rows into canonical edges.

    Supported join_hints shapes per dataset:
    - {"to_dataset": "fruits", "on": ["batch_id"], "note": "optional"}
    - {"joins": [{"to_dataset": "fruits", "on": ["batch_id"], "note": "..."}]}
  """
    by_name = {ds.get("dataset_name"): ds for ds in datasets if ds.get("dataset_name")}
    catalog: list[dict] = []
    seen: set[tuple] = set()

    def _add_edge(from_ds: str, to_ds: str, on: list, note: str = "") -> None:
        if not from_ds or not to_ds or not on:
            return
        key = (from_ds, to_ds, tuple(on))
        if key in seen:
            return
        seen.add(key)
        catalog.append(
            {
                "from_dataset": from_ds,
                "to_dataset": to_ds,
                "on": list(on),
                "note": note or None,
            }
        )

    for ds in datasets:
        from_name = ds.get("dataset_name") or ""
        hints = ds.get("join_hints")
        if not hints:
            continue
        if isinstance(hints, dict):
            joins = hints.get("joins")
            if isinstance(joins, list):
                for item in joins:
                    if not isinstance(item, dict):
                        continue
                    to_ds = item.get("to_dataset") or item.get("target_dataset") or ""
                    on = item.get("on") or item.get("keys") or []
                    if isinstance(on, str):
                        on = [on]
                    _add_edge(from_name, str(to_ds), [str(k) for k in on], str(item.get("note") or ""))
            elif hints.get("to_dataset") or hints.get("target_dataset"):
                to_ds = hints.get("to_dataset") or hints.get("target_dataset") or ""
                on = hints.get("on") or hints.get("keys") or []
                if isinstance(on, str):
                    on = [on]
                _add_edge(from_name, str(to_ds), [str(k) for k in on], str(hints.get("note") or ""))

    for edge in catalog:
        if edge["to_dataset"] not in by_name or edge["from_dataset"] not in by_name:
            continue
    return catalog


def build_full_line_schema(line_name: str, datasets: list[dict]) -> dict:
    if not datasets:
        return {
            "line_name": line_name,
            "datasets": [],
            "join_catalog": [],
            "column_definitions": [],
        }

    datasets_full = [_dataset_full_entry(ds) for ds in datasets]
    join_catalog = normalize_join_catalog(datasets)
    primary = next((d for d in datasets if d.get("role") == "primary"), datasets[0])
    return {
        "line_name": line_name,
        "datasets": datasets_full,
        "join_catalog": join_catalog,
        "column_definitions": primary.get("column_definitions") or [],
    }


async def _distinct_line_names_by_line_name(raw: str) -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GlobalRegistry.line_name)
            .where(
                GlobalRegistry.status == "active",
                or_(
                    GlobalRegistry.line_name == raw,
                    func.lower(GlobalRegistry.line_name) == raw.lower(),
                ),
            )
            .distinct()
        )
        return sorted({row[0] for row in result.all()})


async def _distinct_line_names_by_synonym(raw: str) -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GlobalRegistry.line_name)
            .where(
                GlobalRegistry.status == "active",
                GlobalRegistry.synonyms.contains([raw]),
            )
            .distinct()
        )
        return sorted({row[0] for row in result.all()})


async def _distinct_line_names_by_task_alias(raw: str, user_id: str) -> list[str]:
    if not user_id:
        return []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskRegistry.line_name, TaskRegistry.task_definition).where(
                TaskRegistry.user_id == user_id,
            )
        )
        matches: set[str] = set()
        raw_lower = raw.lower()
        for line_name, task_def in result.all():
            if isinstance(task_def, str):
                import json

                task_def = json.loads(task_def)
            alias = (task_def or {}).get("alias_name") or ""
            if alias.lower() == raw_lower:
                matches.add(line_name)
        return sorted(matches)


def _line_match_from_candidates(
    candidates: list[str], source: str, matched_on: str
) -> LineMatch | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return LineMatch(canonical=candidates[0], source=source, matched_on=matched_on)
    return LineMatch(
        canonical="",
        source="ambiguous",
        matched_on=matched_on,
        candidates=candidates,
    )


async def resolve_line_lookup(mention: str, user_id: str = "") -> LineMatch | None:
    """Ordered line lookup: line_name -> synonym -> task alias."""
    raw = mention.strip()
    if not raw:
        return None

    from agents.manager.debug_log import debug

    candidates = await _distinct_line_names_by_line_name(raw)
    debug("resolve_line_lookup", "step=line_name", mention=raw, candidates=candidates)
    match = _line_match_from_candidates(candidates, "line_name", raw)
    if match:
        return match

    candidates = await _distinct_line_names_by_synonym(raw)
    debug("resolve_line_lookup", "step=synonym", mention=raw, candidates=candidates)
    match = _line_match_from_candidates(candidates, "synonym", raw)
    if match:
        return match

    candidates = await _distinct_line_names_by_task_alias(raw, user_id)
    debug("resolve_line_lookup", "step=task_alias", mention=raw, candidates=candidates)
    match = _line_match_from_candidates(candidates, "task_alias", raw)
    if match:
        return match

    debug("resolve_line_lookup", "step=not_found", mention=raw)
    return None


async def resolve_line_name(name: str) -> str | None:
    match = await resolve_line_lookup(name, user_id="")
    if match is None or match.source == "ambiguous":
        return None
    return match.canonical or None


async def fetch_global_datasets(line_name: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GlobalRegistry)
            .where(GlobalRegistry.line_name == line_name, GlobalRegistry.status == "active")
            .order_by(GlobalRegistry.dataset_name)
        )
        return [_row_to_global_dict(r) for r in result.scalars().all()]


async def fetch_task_versions(user_id: str, line_name: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskRegistry)
            .where(TaskRegistry.user_id == user_id, TaskRegistry.line_name == line_name)
            .order_by(TaskRegistry.version.desc())
        )
        return [_row_to_task_dict(r) for r in result.scalars().all()]


async def save_task_definition(line_name: str, user_id: str, task_definition: dict) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.coalesce(func.max(TaskRegistry.version), 0)).where(
                TaskRegistry.user_id == user_id,
                TaskRegistry.line_name == line_name,
            )
        )
        max_v = result.scalar_one()
        new_version = int(max_v) + 1
        row = TaskRegistry(
            user_id=user_id,
            line_name=line_name,
            version=new_version,
            task_definition=task_definition,
        )
        db.add(row)
        await db.commit()
        return new_version
