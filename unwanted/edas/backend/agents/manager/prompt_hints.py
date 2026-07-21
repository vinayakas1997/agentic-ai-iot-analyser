"""User-facing slot-filling reminder text (line / machine + analysis)."""

LINE_MISSING_HINT = (
    "Which production line or machine is this for?\n"
    "(e.g. AM307A, ZF228)"
)

_AIM_EXAMPLES = "(e.g. sales, downtime, average cost — or ask *what aims can we do*)"

TIER2_EXPLORE_NUDGE = "\n\nFor **3 more analysis options**, say *show me other options*."


def _resolved_line_label(slots: dict | None) -> str | None:
    if not slots:
        return None
    line = slots.get("line") or {}
    if not line.get("resolved"):
        return None
    return (line.get("canonical") or line.get("mention") or "").strip() or None


def format_aim_missing_hint(line_name: str | None = None) -> str:
    if line_name:
        return (
            f"What analysis would you like on **{line_name}**?\n"
            f"{_AIM_EXAMPLES}"
        )
    return f"What analysis would you like to run?\n{_AIM_EXAMPLES}"


def format_advisory_footer(plan: dict | None, line_name: str | None = None) -> str:
    aims = (plan or {}).get("aims") or []
    if aims:
        return "Reply **go** to run this plan, or tell me what to change."
    return format_aim_missing_hint(line_name)


def format_suggested_aims_block(suggested: list[str], *, max_items: int = 3) -> str:
    if not suggested:
        return ""
    shown = suggested[:max_items]
    lines = ["**Suggested aims:**"]
    for a in shown:
        lines.append(f"  - {a}")
    if len(suggested) > max_items:
        lines.append(f"  - ... and {len(suggested) - max_items} more in registry")
    lines.append("\n*(Benefits from IoT team — coming soon)*")
    return "\n".join(lines)


def format_ask_for_missing(missing: list[str], slots: dict | None = None) -> str:
    parts: list[str] = []
    if "line" in missing:
        parts.append(LINE_MISSING_HINT)
    if "aim" in missing:
        line_name = _resolved_line_label(slots) if "line" not in missing else None
        parts.append(format_aim_missing_hint(line_name))
    return "\n\n".join(parts)
