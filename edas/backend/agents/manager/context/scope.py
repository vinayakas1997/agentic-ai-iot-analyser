"""Scope Context Service — multi-line intent and active line summary."""

from __future__ import annotations


def build_scope_inventory(slots: dict | None) -> dict:
    slots = slots or {}
    scope = slots.get("scope") or {}
    line_slots = slots.get("line_slots") or []
    line = slots.get("line") or {}

    entries = []
    for s in line_slots:
        entries.append(
            {
                "mention": s.get("mention"),
                "canonical": s.get("canonical"),
                "status": s.get("status"),
                "skipped": bool(s.get("skipped")),
                "resolved": bool(s.get("resolved")),
            }
        )

    resolved = [e for e in entries if e.get("status") == "resolved" and not e.get("skipped")]
    active_idx = slots.get("active_line_index")
    active_canonical = line.get("canonical")
    if active_idx is not None and active_idx < len(line_slots):
        active_canonical = line_slots[active_idx].get("canonical") or active_canonical

    return {
        "intent_mode": scope.get("intent_mode") or "single",
        "slot_count": len(line_slots),
        "resolved_count": len(resolved),
        "active_line": active_canonical,
        "active_mention": line.get("mention"),
        "line_entries": entries,
        "joint_aim_raw": scope.get("joint_aim_raw"),
        "joint_time_raw": scope.get("joint_time_raw"),
    }


def format_scope_for_prompt(inventory: dict | None) -> str:
    inv = inventory or {}
    mode = inv.get("intent_mode") or "single"
    lines = [f"Scope: {mode}"]
    active = inv.get("active_line")
    if active:
        lines.append(f"Active line: **{active}**")
    for e in inv.get("line_entries") or []:
        if e.get("skipped"):
            continue
        label = e.get("canonical") or e.get("mention") or "?"
        lines.append(f"  - {e.get('mention')} → {label} ({e.get('status')})")
    return "\n".join(lines)
