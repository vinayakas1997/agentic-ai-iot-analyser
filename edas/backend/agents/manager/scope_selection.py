"""Machine scope selection for explore / propose (numbered CLI menu)."""

from __future__ import annotations

from agents.manager.slot_inventory import sync_active_line


def resolved_line_slots(slots: dict) -> list[dict]:
    return [
        s
        for s in slots.get("line_slots") or []
        if s.get("status") == "resolved" and not s.get("skipped") and s.get("canonical")
    ]


def count_resolved_lines(slots: dict) -> int:
    return len(resolved_line_slots(slots))


def auto_scope_if_single(slots: dict) -> tuple[dict, str | None, bool]:
    """Single resolved line → set scope without prompt. Returns (slots, selection, pending)."""
    resolved = resolved_line_slots(slots)
    if len(resolved) != 1:
        return slots, None, len(resolved) > 1
    canonical = resolved[0].get("canonical")
    slots = dict(slots)
    slots["scope"] = {**(slots.get("scope") or {}), "intent_mode": "single"}
    return slots, canonical, False


def needs_scope_prompt(state: dict) -> bool:
    if state.get("scope_selection"):
        return False
    if not state.get("scope_pending"):
        return False
    action = (state.get("aim_exploration") or {}).get("action")
    if action not in ("propose", "refine"):
        return False
    slots = state.get("slots") or {}
    return count_resolved_lines(slots) > 1


def format_scope_menu(slots: dict) -> str:
    resolved = resolved_line_slots(slots)
    lines = [
        "Which machine(s) should I use for these options?",
        "",
        "**1.** All machines (joint analysis)",
    ]
    for i, slot in enumerate(resolved, start=2):
        mention = slot.get("mention") or slot.get("canonical")
        canonical = slot.get("canonical")
        lines.append(f"**{i}.** {canonical} ({mention})")
    lines.append("")
    lines.append("Reply with the number (e.g. **1** or **2**).")
    return "\n".join(lines)


def parse_scope_reply(user_message: str, slots: dict) -> str | None:
    text = user_message.strip().lower()
    resolved = resolved_line_slots(slots)
    if not resolved:
        return None
    if text in ("1", "all", "all machines", "joint", "both"):
        return "all"
    if text.isdigit():
        idx = int(text)
        if idx == 1:
            return "all"
        pos = idx - 2
        if 0 <= pos < len(resolved):
            return str(resolved[pos].get("canonical") or "")
    if text.startswith("scope "):
        return text[6:].strip()
    for slot in resolved:
        canonical = (slot.get("canonical") or "").lower()
        mention = (slot.get("mention") or "").lower()
        if canonical and canonical in text:
            return slot.get("canonical")
        if mention and mention in text:
            return slot.get("canonical")
    return None


def apply_scope_selection(slots: dict, selection: str) -> dict:
    slots = dict(slots)
    resolved = resolved_line_slots(slots)
    line_slots = [dict(s) for s in slots.get("line_slots") or []]
    scope = dict(slots.get("scope") or {})

    if selection == "all":
        scope["intent_mode"] = "joint"
        slots["scope"] = scope
        slots["line_slots"] = line_slots
        return slots

    scope["intent_mode"] = "single"
    slots["scope"] = scope
    for i, slot in enumerate(line_slots):
        if (slot.get("canonical") or "").lower() == selection.lower():
            slots["active_line_index"] = i
            break
        if (slot.get("mention") or "").lower() == selection.lower():
            slots["active_line_index"] = i
            break
    slots["line_slots"] = line_slots
    return sync_active_line(slots)


def set_scope_pending_for_propose(state: dict) -> dict:
    """Mark scope_pending when multi-line and propose without selection."""
    slots = state.get("slots") or {}
    resolved = resolved_line_slots(slots)
    action = (state.get("aim_exploration") or {}).get("action")
    if action not in ("propose", "refine"):
        return {**state, "scope_pending": False}
    if len(resolved) <= 1:
        slots, sel, _ = auto_scope_if_single(slots)
        return {**state, "slots": slots, "scope_selection": sel, "scope_pending": False}
    if state.get("scope_selection"):
        return {**state, "scope_pending": False}
    return {**state, "scope_pending": True}
