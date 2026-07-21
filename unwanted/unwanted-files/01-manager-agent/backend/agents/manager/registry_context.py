"""Registry Context Service — fetch, resolve, filter line/dataset schema for Manager prompts."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Any

from agents.manager.db import (
    build_full_line_schema,
    build_schema_state,
    fetch_global_datasets,
    normalize_join_catalog,
)

logger = logging.getLogger(__name__)


def _normalize_mention(text: str) -> str:
    return re.sub(r"[_\-]+", " ", (text or "").lower().strip())


def _dataset_table_name(ds: dict) -> str:
    cfg = ds.get("source_config") or {}
    return str(cfg.get("table") or cfg.get("path") or "")


def _norm_token(text: str) -> str:
    return re.sub(r"[_\-\s]+", "", (text or "").lower())


def resolve_dataset_on_line(
    _line_name: str,
    mention: str,
    datasets: list[dict] | None = None,
    *,
    datasets_full: list[dict] | None = None,
) -> str | None:
    """Match user text to dataset_name or physical table name on a line."""
    raw = (mention or "").strip()
    if not raw:
        return None

    norm_mention = _normalize_mention(raw)
    norm_compact = _norm_token(raw)

    entries: list[dict] = []
    if datasets_full:
        for ds in datasets_full:
            entries.append(
                {
                    "dataset_name": ds.get("dataset_name"),
                    "table": ds.get("table") or "",
                }
            )
    elif datasets:
        for ds in datasets:
            entries.append(
                {
                    "dataset_name": ds.get("dataset_name"),
                    "table": _dataset_table_name(ds),
                }
            )

    if not entries:
        return None

    # Exact dataset_name
    for e in entries:
        name = e.get("dataset_name") or ""
        if _normalize_mention(name) == norm_mention or _norm_token(name) == norm_compact:
            return name

    # Exact table name
    for e in entries:
        table = e.get("table") or ""
        if _normalize_mention(table) == norm_mention or _norm_token(table) == norm_compact:
            return e.get("dataset_name")

    # Substring: "quality" -> fruit_quality, test_fruit_quality
    matches: list[str] = []
    for e in entries:
        name = e.get("dataset_name") or ""
        table = e.get("table") or ""
        name_norm = _normalize_mention(name)
        table_norm = _normalize_mention(table)
        if (
            norm_mention in name_norm
            or name_norm in norm_mention
            or norm_compact in _norm_token(name)
            or norm_mention in table_norm
            or table_norm in norm_mention
            or norm_compact in _norm_token(table)
        ):
            matches.append(name)

    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        return unique[0]
    return None


def apply_dataset_policy(
    full_schema: dict,
    included: list[str] | None,
    excluded: list[str] | None,
    *,
    raw_datasets: list[dict] | None = None,
) -> dict:
    """Return filtered datasets_full and join_catalog; exclude always wins."""
    datasets_full = list(full_schema.get("datasets") or [])
    join_catalog = list(full_schema.get("join_catalog") or [])
    all_names = [d.get("dataset_name") for d in datasets_full if d.get("dataset_name")]

    excluded_set = {n for n in (excluded or []) if n in all_names}
    if included:
        included_set = {n for n in included if n in all_names and n not in excluded_set}
    else:
        primary = next(
            (d.get("dataset_name") for d in datasets_full if d.get("role") == "primary"),
            all_names[0] if all_names else None,
        )
        included_set = {primary} if primary and primary not in excluded_set else set()

    if not included_set and all_names:
        included_set = {n for n in all_names if n not in excluded_set}

    filtered_datasets = [d for d in datasets_full if d.get("dataset_name") in included_set]
    in_scope = {d.get("dataset_name") for d in filtered_datasets}
    filtered_joins = [
        e
        for e in join_catalog
        if e.get("from_dataset") in in_scope and e.get("to_dataset") in in_scope
    ]

    primary_cols: list[dict] = []
    if raw_datasets:
        primary = next((d for d in raw_datasets if d.get("role") == "primary"), raw_datasets[0] if raw_datasets else {})
        primary_cols = primary.get("column_definitions") or []
    elif filtered_datasets:
        primary_entry = next((d for d in filtered_datasets if d.get("role") == "primary"), filtered_datasets[0])
        primary_cols = primary_entry.get("column_definitions") or []

    return {
        "line_name": full_schema.get("line_name"),
        "datasets": filtered_datasets,
        "join_catalog": filtered_joins,
        "column_definitions": primary_cols,
        "included": sorted(included_set),
        "excluded": sorted(excluded_set),
    }


async def fetch_line_bundle(line_name: str) -> dict | None:
    """Fetch all datasets for a line and build full schema bundle."""
    datasets = await fetch_global_datasets(line_name)
    if not datasets:
        return None
    full = build_full_line_schema(line_name, datasets)
    schema = build_schema_state(line_name, datasets)
    global_version = schema.get("global_version", 1)
    return {
        "line_name": line_name,
        "datasets": datasets,
        "full_schema": full,
        "schema": schema,
        "global_version": global_version,
        "dataset_names": [d.get("dataset_name") for d in full.get("datasets") or [] if d.get("dataset_name")],
    }


def empty_dataset_context() -> dict:
    return {"by_line": {}, "active_line": None, "pending_mentions": [], "pending_exclude": [], "pending_include": []}


def empty_line_dataset_entry() -> dict:
    return {
        "loaded": False,
        "global_version": None,
        "included": [],
        "excluded": [],
        "mentioned": [],
        "available": [],
    }


def get_line_dataset_entry(dataset_context: dict | None, line_name: str) -> dict:
    ctx = dataset_context or empty_dataset_context()
    by_line = dict(ctx.get("by_line") or {})
    if line_name not in by_line:
        by_line[line_name] = empty_line_dataset_entry()
    return by_line[line_name]


def merge_dataset_intent_from_clarification(
    dataset_context: dict | None,
    clarification: dict | None,
    active_line: str | None,
) -> dict:
    """Apply dataset_mentions / include / exclude from extract_slots clarification."""
    ctx = deepcopy(dataset_context or empty_dataset_context())
    clar = clarification or {}

    for key, target in (
        ("dataset_mentions", "pending_mentions"),
        ("exclude_datasets", "pending_exclude"),
        ("include_datasets", "pending_include"),
    ):
        vals = clar.get(key)
        if isinstance(vals, list) and vals:
            existing = list(ctx.get(target) or [])
            for v in vals:
                s = str(v).strip()
                if s and s not in existing:
                    existing.append(s)
            ctx[target] = existing

    if active_line:
        ctx["active_line"] = active_line
    return ctx


def _primary_dataset_name(bundle: dict) -> str | None:
    datasets = bundle.get("datasets") or []
    primary = next((d for d in datasets if d.get("role") == "primary"), datasets[0] if datasets else None)
    return primary.get("dataset_name") if primary else None


def _resolve_pending_names(
    line_name: str,
    bundle: dict,
    pending: list[str],
) -> list[str]:
    resolved: list[str] = []
    full_schema = bundle.get("full_schema") or {}
    datasets_full = full_schema.get("datasets") or []
    raw = bundle.get("datasets") or []
    for mention in pending:
        name = resolve_dataset_on_line(
            line_name, mention, datasets=raw, datasets_full=datasets_full
        )
        if name and name not in resolved:
            resolved.append(name)
    return resolved


def apply_policy_to_line_entry(
    line_name: str,
    entry: dict,
    bundle: dict,
) -> dict:
    """Compute included/excluded/mentioned for one line from bundle + entry state."""
    full_schema = bundle.get("full_schema") or {}
    all_names = bundle.get("dataset_names") or []
    primary = _primary_dataset_name(bundle)

    mentioned = list(entry.get("mentioned") or [])
    for m in _resolve_pending_names(line_name, bundle, entry.get("_pending_mentions") or []):
        if m not in mentioned:
            mentioned.append(m)

    excluded = list(entry.get("excluded") or [])
    for m in _resolve_pending_names(line_name, bundle, entry.get("_pending_exclude") or []):
        if m not in excluded:
            excluded.append(m)

    included = list(entry.get("included") or [])
    for m in _resolve_pending_names(line_name, bundle, entry.get("_pending_include") or []):
        if m not in included:
            included.append(m)
    for m in mentioned:
        if m not in included:
            included.append(m)

    if not included and primary:
        included = [primary]

    filtered = apply_dataset_policy(
        full_schema,
        included,
        excluded,
        raw_datasets=bundle.get("datasets"),
    )

    return {
        "loaded": True,
        "global_version": bundle.get("global_version"),
        "available": all_names,
        "mentioned": mentioned,
        "excluded": sorted(filtered.get("excluded") or []),
        "included": sorted(filtered.get("included") or []),
        "full_schema": full_schema,
        "filtered_schema": {
            "line_name": line_name,
            "datasets": filtered.get("datasets") or [],
            "join_catalog": filtered.get("join_catalog") or [],
            "column_definitions": filtered.get("column_definitions") or [],
        },
        "bundle": {
            "datasets": bundle.get("datasets"),
            "schema": bundle.get("schema"),
            "global_version": bundle.get("global_version"),
        },
    }


def format_line_context_from_entry(line_name: str, entry: dict) -> dict:
    """Build line_context dict from a synced line dataset entry."""
    bundle = entry.get("bundle") or {}
    datasets = bundle.get("datasets") or []
    schema = deepcopy(bundle.get("schema") or {})
    filtered = entry.get("filtered_schema") or {}
    datasets_full = filtered.get("datasets") or []
    join_catalog = filtered.get("join_catalog") or []

    col_preview = []
    column_count = 0
    for ds in datasets_full:
        cols = ds.get("column_definitions") or []
        column_count += len(cols)
        for c in cols[:5]:
            col_preview.append(
                {
                    "name": c.get("name"),
                    "datatype": c.get("datatype"),
                    "meaning": c.get("meaning"),
                    "dataset_name": ds.get("dataset_name"),
                }
            )

    suggested: list[str] = []
    included_set = set(entry.get("included") or [])
    for ds in datasets:
        if ds.get("dataset_name") not in included_set:
            continue
        for aim in ds.get("suggested_aims") or []:
            if aim not in suggested:
                suggested.append(aim)

    dataset_summaries = []
    for ds in datasets_full:
        dataset_summaries.append(
            {
                "dataset_name": ds.get("dataset_name"),
                "table": ds.get("table"),
                "role": ds.get("role"),
                "description": ds.get("description"),
                "data_earliest_ts": ds.get("data_earliest_ts"),
            }
        )

    schema["datasets_full"] = datasets_full
    schema["join_catalog"] = join_catalog
    schema["column_definitions"] = filtered.get("column_definitions") or schema.get("column_definitions") or []

    filtered_datasets = [d for d in datasets if d.get("dataset_name") in included_set]

    return {
        "line_name": line_name,
        "datasets": filtered_datasets,
        "schema": schema,
        "datasets_full": datasets_full,
        "join_catalog": join_catalog,
        "dataset_summaries": dataset_summaries,
        "column_preview": col_preview[:10],
        "column_count": column_count,
        "suggested_aims": suggested,
        "datasets_in_scope": sorted(included_set),
        "datasets_excluded": list(entry.get("excluded") or []),
    }


def build_context_inventory(
    dataset_context: dict | None,
    *,
    slots: dict | None = None,
) -> dict:
    """Machine-readable summary of loaded machines, tables, included/excluded."""
    ctx = dataset_context or empty_dataset_context()
    by_line = ctx.get("by_line") or {}
    active = ctx.get("active_line")
    if not active and slots:
        active = (slots.get("line") or {}).get("canonical")

    lines_summary = []
    for line_name, entry in by_line.items():
        if not entry.get("loaded"):
            continue
        lines_summary.append(
            {
                "line_name": line_name,
                "available_datasets": entry.get("available") or [],
                "included_datasets": entry.get("included") or [],
                "excluded_datasets": entry.get("excluded") or [],
                "mentioned_datasets": entry.get("mentioned") or [],
            }
        )

    active_entry = by_line.get(active) if active else None
    return {
        "active_line": active,
        "lines": lines_summary,
        "included_datasets": list(active_entry.get("included") or []) if active_entry else [],
        "excluded_datasets": list(active_entry.get("excluded") or []) if active_entry else [],
        "available_datasets": list(active_entry.get("available") or []) if active_entry else [],
    }


def build_planner_schema_payload(line_context: dict | None, dataset_context: dict | None) -> dict:
    """Filtered schema slice for planner_payload handoff."""
    if not line_context:
        return {
            "datasets_in_scope": [],
            "datasets_excluded": [],
            "dataset_schemas": [],
            "join_catalog": [],
        }
    line_name = line_context.get("line_name")
    entry = (dataset_context or {}).get("by_line", {}).get(line_name) or {}
    return {
        "datasets_in_scope": line_context.get("datasets_in_scope") or entry.get("included") or [],
        "datasets_excluded": line_context.get("datasets_excluded") or entry.get("excluded") or [],
        "dataset_schemas": line_context.get("datasets_full") or [],
        "join_catalog": line_context.get("join_catalog") or [],
    }


async def sync_dataset_context_for_state(
    slots: dict,
    dataset_context: dict | None,
    *,
    fetch_fn=fetch_line_bundle,
) -> tuple[dict, dict | None, dict | None, dict | None]:
    """Sync all resolved lines; return (dataset_context, line_context, explore_context, error_info)."""
    def _resolved_line_slots(slots_dict: dict) -> list[dict]:
        return [
            s
            for s in slots_dict.get("line_slots") or []
            if s.get("status") == "resolved" and not s.get("skipped") and s.get("canonical")
        ]

    ctx = deepcopy(dataset_context or empty_dataset_context())
    resolved = _resolved_line_slots(slots)
    active_line = (slots.get("line") or {}).get("canonical")
    if active_line:
        ctx["active_line"] = active_line

    pending_mentions = list(ctx.pop("pending_mentions", None) or [])
    pending_exclude = list(ctx.pop("pending_exclude", None) or [])
    pending_include = list(ctx.pop("pending_include", None) or [])

    by_line = dict(ctx.get("by_line") or {})
    error_info = None

    for slot in resolved:
        canonical = slot.get("canonical")
        if not canonical:
            continue

        prev = dict(by_line.get(canonical) or empty_line_dataset_entry())
        prev["_pending_mentions"] = list(pending_mentions)
        prev["_pending_exclude"] = list(pending_exclude)
        prev["_pending_include"] = list(pending_include)

        cached_version = prev.get("global_version")
        need_fetch = not prev.get("loaded") or prev.get("full_schema") is None

        bundle = None
        if not need_fetch and prev.get("bundle"):
            bundle = {
                "line_name": canonical,
                "datasets": (prev.get("bundle") or {}).get("datasets"),
                "full_schema": prev.get("full_schema"),
                "schema": (prev.get("bundle") or {}).get("schema"),
                "global_version": cached_version,
                "dataset_names": prev.get("available") or [],
            }

        if need_fetch or bundle is None:
            try:
                fetched = await fetch_fn(canonical)
            except Exception:
                logger.exception("sync_dataset_context_for_state: fetch failed for %s", canonical)
                error_info = {"error": "no_datasets", "line": canonical}
                continue
            if fetched is None:
                error_info = {"error": "no_datasets", "line": canonical}
                continue
            if cached_version is not None and fetched.get("global_version") == cached_version and prev.get("full_schema"):
                bundle = {
                    "line_name": canonical,
                    "datasets": fetched.get("datasets"),
                    "full_schema": prev.get("full_schema"),
                    "schema": fetched.get("schema"),
                    "global_version": cached_version,
                    "dataset_names": fetched.get("dataset_names"),
                }
            else:
                bundle = fetched

        entry = apply_policy_to_line_entry(canonical, prev, bundle)
        for k in ("_pending_mentions", "_pending_exclude", "_pending_include"):
            entry.pop(k, None)
        by_line[canonical] = entry

    ctx["by_line"] = by_line
    ctx["pending_mentions"] = []
    ctx["pending_exclude"] = []
    ctx["pending_include"] = []

    if error_info and not by_line:
        return ctx, None, None, error_info

    primary_canonical = active_line or (resolved[0].get("canonical") if resolved else None)
    line_context = None
    explore_context = None

    if primary_canonical and primary_canonical in by_line:
        line_context = format_line_context_from_entry(primary_canonical, by_line[primary_canonical])

    scope = slots.get("scope") or {}
    intent_mode = scope.get("intent_mode")
    if len(resolved) >= 2 and intent_mode == "joint":
        line_entries = []
        for slot in resolved:
            canonical = slot.get("canonical")
            if not canonical or canonical not in by_line:
                continue
            entry = by_line[canonical]
            filtered = entry.get("filtered_schema") or {}
            line_entries.append(
                {
                    "line_name": canonical,
                    "mention": slot.get("mention"),
                    "datasets_full": filtered.get("datasets") or [],
                    "join_catalog": filtered.get("join_catalog") or [],
                    "suggested_aims": format_line_context_from_entry(canonical, entry).get("suggested_aims") or [],
                    "dataset_summaries": [
                        {
                            "dataset_name": d.get("dataset_name"),
                            "table": d.get("table"),
                            "role": d.get("role"),
                        }
                        for d in filtered.get("datasets") or []
                    ],
                }
            )
        if line_entries:
            names = [e["line_name"] for e in line_entries]
            explore_context = {
                "mode": "multi_line",
                "lines": line_entries,
                "line_label": " + ".join(names),
            }
    elif primary_canonical and primary_canonical in by_line:
        entry = by_line[primary_canonical]
        filtered = entry.get("filtered_schema") or {}
        explore_context = {
            "mode": "single_line",
            "lines": [
                {
                    "line_name": primary_canonical,
                    "datasets_full": filtered.get("datasets") or [],
                    "join_catalog": filtered.get("join_catalog") or [],
                    "suggested_aims": line_context.get("suggested_aims") if line_context else [],
                    "dataset_summaries": line_context.get("dataset_summaries") if line_context else [],
                }
            ],
            "line_label": primary_canonical,
        }

    return ctx, line_context, explore_context, error_info
