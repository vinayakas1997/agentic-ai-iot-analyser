"""Join Context Service — known joins and column-overlap suggestions."""

from __future__ import annotations


def _column_names(datasets_full: list[dict]) -> dict[str, set[str]]:
    by_ds: dict[str, set[str]] = {}
    for ds in datasets_full:
        name = ds.get("dataset_name")
        if not name:
            continue
        cols = ds.get("column_definitions") or []
        by_ds[name] = {str(c.get("name")) for c in cols if c.get("name")}
    return by_ds


def suggest_join_candidates(datasets_full: list[dict]) -> list[dict]:
    """Suggest join keys from overlapping column names (labeled as suggestions only)."""
    by_ds = _column_names(datasets_full)
    names = list(by_ds.keys())
    suggestions: list[dict] = []
    seen: set[tuple] = set()

    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            overlap = by_ds[a] & by_ds[b]
            for col in sorted(overlap):
                key = (a, b, col)
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append(
                    {
                        "from_dataset": a,
                        "to_dataset": b,
                        "on": [col],
                        "note": "suggested from matching column names",
                    }
                )
    return suggestions


def build_join_inventory(
    line_context: dict | None,
    *,
    include_suggestions: bool = True,
) -> dict:
    ctx = line_context or {}
    known = list(ctx.get("join_catalog") or [])
    datasets_full = list(ctx.get("datasets_full") or [])
    suggestions = suggest_join_candidates(datasets_full) if include_suggestions else []

    known_keys = {(e.get("from_dataset"), e.get("to_dataset"), tuple(e.get("on") or [])) for e in known}
    filtered_suggestions = [
        s
        for s in suggestions
        if (s.get("from_dataset"), s.get("to_dataset"), tuple(s.get("on") or [])) not in known_keys
    ]

    return {
        "known_joins": known,
        "suggested_joins": filtered_suggestions,
        "datasets_in_scope": [d.get("dataset_name") for d in datasets_full if d.get("dataset_name")],
    }


def format_join_for_prompt(inventory: dict | None) -> str:
    inv = inventory or {}
    lines: list[str] = []
    known = inv.get("known_joins") or []
    if known:
        lines.append("Known joins:")
        for e in known:
            on = ", ".join(e.get("on") or [])
            lines.append(f"  - {e.get('from_dataset')}.{on} → {e.get('to_dataset')}.{on}")
    suggested = inv.get("suggested_joins") or []
    if suggested:
        lines.append("Suggested joins (verify before use):")
        for e in suggested[:5]:
            on = ", ".join(e.get("on") or [])
            lines.append(f"  - {e.get('from_dataset')}.{on} → {e.get('to_dataset')}.{on}")
    if not lines:
        return "Joins: none known"
    return "\n".join(lines)
