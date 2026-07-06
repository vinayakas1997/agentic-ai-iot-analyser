"""Format line schema and join catalog for LLM prompts and user messages."""

from __future__ import annotations


def format_context_inventory_for_prompt(
    dataset_context: dict | None = None,
    *,
    slots: dict | None = None,
    state: dict | None = None,
) -> str:
    if state and state.get("session_inventory"):
        from agents.manager.context.session_inventory import format_session_inventory_for_prompt

        return format_session_inventory_for_prompt(state)

    from agents.manager.registry_context import build_context_inventory

    inventory = build_context_inventory(dataset_context, slots=slots)
    if not inventory.get("lines"):
        return "(no registry context loaded)"

    lines: list[str] = []
    for line_info in inventory.get("lines") or []:
        name = line_info.get("line_name")
        avail = ", ".join(line_info.get("available_datasets") or []) or "none"
        inc = ", ".join(line_info.get("included_datasets") or []) or "none"
        exc = ", ".join(line_info.get("excluded_datasets") or []) or "none"
        lines.append(
            f"- **{name}**: loaded [{avail}]; in scope [{inc}]; excluded [{exc}]"
        )
    active = inventory.get("active_line")
    header = f"Active line: **{active}**\n" if active else ""
    return header + "\n".join(lines)


def format_datasets_for_prompt(
    line_context: dict | None = None,
    *,
    explore_context: dict | None = None,
    cols_per_dataset: int = 12,
) -> str:
    if explore_context and explore_context.get("mode") == "multi_line":
        blocks: list[str] = []
        for line_entry in explore_context.get("lines") or []:
            blocks.append(f"### Line: {line_entry.get('line_name')}")
            blocks.append(_format_single_line_datasets(line_entry, cols_per_dataset))
        return "\n\n".join(blocks) if blocks else "(no datasets)"

    if line_context:
        return _format_single_line_datasets(line_context, cols_per_dataset)
    return "(no datasets)"


def _format_single_line_datasets(ctx: dict, cols_per_dataset: int) -> str:
    datasets_full = ctx.get("datasets_full") or []
    if not datasets_full:
        summaries = ctx.get("dataset_summaries") or []
        if not summaries:
            return "(no datasets)"
        lines = []
        for ds in summaries:
            lines.append(
                f"- **{ds.get('dataset_name')}** → `{ds.get('table')}` ({ds.get('role') or 'dataset'})"
            )
        return "\n".join(lines)

    blocks: list[str] = []
    for ds in datasets_full:
        blocks.append(
            f"**{ds.get('dataset_name')}** → `{ds.get('table')}` ({ds.get('role') or 'dataset'})"
        )
        if ds.get("description"):
            blocks.append(f"  Description: {ds['description']}")
        cols = ds.get("column_definitions") or []
        if cols:
            blocks.append("  Columns:")
            for c in cols[:cols_per_dataset]:
                blocks.append(
                    f"    - `{c.get('name')}` ({c.get('datatype')}): {c.get('meaning')}"
                )
            extra = len(cols) - cols_per_dataset
            if extra > 0:
                blocks.append(f"    - ... and {extra} more columns")
        hints = ds.get("join_hints")
        if hints:
            blocks.append(f"  Join hints: {hints}")
        aims = ds.get("suggested_aims") or []
        if aims:
            blocks.append("  Suggested aims: " + "; ".join(aims))
        blocks.append("")
    return "\n".join(blocks).strip()


def format_join_catalog_for_prompt(
    line_context: dict | None = None,
    *,
    explore_context: dict | None = None,
) -> str:
    if explore_context and explore_context.get("mode") == "multi_line":
        blocks: list[str] = []
        for line_entry in explore_context.get("lines") or []:
            catalog = line_entry.get("join_catalog") or []
            if not catalog:
                continue
            blocks.append(f"**{line_entry.get('line_name')}:**")
            blocks.extend(_format_join_edges(catalog))
        return "\n".join(blocks) if blocks else "(no known joins)"

    catalog = (line_context or {}).get("join_catalog") or []
    if not catalog:
        return "(no known joins)"
    return "\n".join(_format_join_edges(catalog))


def _format_join_edges(catalog: list[dict]) -> list[str]:
    lines: list[str] = []
    for edge in catalog:
        on = ", ".join(edge.get("on") or [])
        note = f" — {edge['note']}" if edge.get("note") else ""
        lines.append(
            f"  - {edge.get('from_dataset')}.{on} → {edge.get('to_dataset')}.{on}{note}"
        )
    return lines


def format_join_catalog_user_block(line_context: dict | None) -> str:
    catalog = (line_context or {}).get("join_catalog") or []
    if not catalog:
        return ""
    lines = ["**Known joins:**"]
    lines.extend(_format_join_edges(catalog))
    return "\n".join(lines)


def format_multi_dataset_columns_user_block(line_context: dict | None, *, preview: int = 5) -> str:
    datasets_full = (line_context or {}).get("datasets_full") or []
    if len(datasets_full) <= 1:
        return ""

    blocks: list[str] = ["**Columns by dataset:**"]
    for ds in datasets_full:
        cols = ds.get("column_definitions") or []
        col_names = [c.get("name") for c in cols[:preview] if c.get("name")]
        extra = len(cols) - len(col_names)
        suffix = f", ... +{extra} more" if extra > 0 else ""
        blocks.append(f"  - **{ds.get('dataset_name')}**: {', '.join(col_names)}{suffix}")
    return "\n".join(blocks)


def explore_context_label(explore_context: dict | None, fallback: str) -> str:
    if not explore_context:
        return fallback
    if explore_context.get("line_label"):
        return str(explore_context["line_label"])
    if explore_context.get("mode") == "multi_line":
        names = [ln.get("line_name") for ln in explore_context.get("lines") or [] if ln.get("line_name")]
        if names:
            return " + ".join(names)
    return fallback
