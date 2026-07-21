"""Client-aware user message assembly (CLI verbose vs web short)."""

from __future__ import annotations

import re

from agents.manager.constants import SOURCE_LABELS
from agents.manager.prompt_hints import format_suggested_aims_block
from agents.manager.schema_format import (
    format_join_catalog_user_block,
    format_multi_dataset_columns_user_block,
)


def _normalize_line_token(value: str | None) -> str:
    return re.sub(r"[_\-]+", " ", (value or "").lower().strip())


def format_line_match_note(slots: dict) -> str:
    line = slots.get("line") or {}
    mention = line.get("mention")
    canonical = line.get("canonical")
    source = line.get("source")
    if not mention or not canonical or not source:
        return ""
    if _normalize_line_token(mention) == _normalize_line_token(canonical):
        return ""
    label = SOURCE_LABELS.get(source, source)
    return f'You said **"{mention}"** — matched via **{label}** to line **{canonical}**.'


def format_web_body_suggested_aims(canonical: str) -> str:
    return (
        f"I've loaded analysis options for **{canonical}**. "
        "You can pick any suggested aim from Context or Outputs, or describe your own analysis in chat."
    )

def format_time_range_note(slots: dict) -> str:
    time_slot = slots.get("time") or {}
    if not time_slot.get("resolved"):
        return ""
    if time_slot.get("no_filter"):
        return ""
    if not time_slot.get("start") and not time_slot.get("end"):
        return ""
    raw = time_slot.get("raw") or ""
    raw_note = f' (from "{raw}")' if raw else ""
    return f"**Time range:** {time_slot.get('start')} → {time_slot.get('end')}{raw_note}"


def format_line_info_cli(
    line_context: dict | None,
    slots: dict | None = None,
    *,
    brief: bool = False,
) -> str:
    parts: list[str] = []
    if slots:
        match_note = format_line_match_note(slots)
        if match_note:
            parts.append(match_note)
        time_note = format_time_range_note(slots)
        if time_note:
            parts.append(time_note)

    if not line_context:
        return "\n\n".join(parts)

    if brief:
        parts.append(f"**Line:** {line_context['line_name']}")
        return "\n\n".join(parts)

    summaries = line_context.get("dataset_summaries") or []
    ds_lines = []
    for ds in summaries:
        ds_lines.append(f"  - **{ds['dataset_name']}** → `{ds['table']}` ({ds.get('role') or 'dataset'})")

    join_block = format_join_catalog_user_block(line_context)
    multi_col_block = format_multi_dataset_columns_user_block(line_context)

    if multi_col_block:
        col_section = multi_col_block
    else:
        cols = line_context.get("column_preview") or []
        col_lines = [f"  - `{c['name']}` ({c.get('datatype')}): {c.get('meaning')}" for c in cols]
        extra = line_context.get("column_count", 0) - len(cols)
        if extra > 0:
            col_lines.append(f"  - ... and {extra} more columns")
        col_section = "**Columns:**\n" + "\n".join(col_lines)

    suggested = line_context.get("suggested_aims") or []
    suggested_block = format_suggested_aims_block(suggested)
    if suggested_block:
        suggested_block = "\n" + suggested_block

    join_section = f"\n{join_block}" if join_block else ""
    parts.append(
        f"**Line:** {line_context['line_name']}\n"
        f"**Datasets:**\n" + "\n".join(ds_lines) + "\n"
        f"{col_section}" + join_section + suggested_block
    )
    return "\n\n".join(parts)


def format_web_body_after_line_resolve(slots: dict, line_context: dict | None) -> str:
    match_note = format_line_match_note(slots)
    if match_note:
        return f"{match_note} See Context for full details."
    line = slots.get("line") or {}
    canonical = line.get("canonical") or (line_context or {}).get("line_name") or "this line"
    mention = line.get("mention") or canonical
    if mention != canonical:
        return f"I've loaded **{canonical}** (from **{mention}**). See Context for full details."
    return f"I've loaded **{canonical}**. See Context for full details."


def assemble_reply(
    *,
    client: str,
    body: str,
    context_block: str = "",
    next_step: str = "",
) -> tuple[str, str | None]:
    """Return (agent_message, message_next_step). next_step is set only for web."""
    parts = [p for p in (body.strip(), context_block.strip(), next_step.strip()) if p]
    if client == "web":
        return body.strip(), next_step.strip() or None
    return "\n\n".join(parts), None
