"""Plan / Explore Context Service — proposals and confirmed plan summary."""

from __future__ import annotations


def build_plan_explore_inventory(state: dict) -> dict:
    plan = state.get("plan") or {}
    slots = state.get("slots") or {}
    aim = slots.get("aim") or {}
    proposals = state.get("analysis_proposals") or []
    saved = state.get("saved_plans") or []

    proposal_summary = [
        {
            "id": p.get("id"),
            "title": p.get("title"),
            "datasets_used": p.get("datasets_used") or [],
        }
        for p in proposals
        if isinstance(p, dict)
    ]

    saved_summary = [
        {"id": p.get("id"), "title": p.get("title")}
        for p in saved
        if isinstance(p, dict)
    ]

    aims = plan.get("aims") or aim.get("aims") or []
    return {
        "explore_phase": state.get("explore_phase"),
        "wants_suggested_aims": bool(state.get("wants_suggested_aims")),
        "proposal_count": len(proposal_summary),
        "proposals": proposal_summary,
        "saved_plan_count": len(saved_summary),
        "saved_plans": saved_summary,
        "scope_selection": state.get("scope_selection"),
        "scope_pending": bool(state.get("scope_pending")),
        "has_plan": bool(plan.get("aims") or aims),
        "plan_aims": list(aims),
        "plan_line": plan.get("line"),
        "tier": _tier_label(state),
    }


def _tier_label(state: dict) -> str:
    if state.get("analysis_proposals"):
        return "tier2_explore"
    if state.get("saved_plans"):
        return "saved_shortlist"
    if state.get("wants_suggested_aims"):
        return "tier1_registry"
    if state.get("plan"):
        return "confirmed_plan"
    return "none"


def format_plan_explore_for_prompt(inventory: dict | None) -> str:
    inv = inventory or {}
    lines = [f"Explore: {inv.get('tier') or 'none'}"]
    if inv.get("scope_selection"):
        lines.append(f"Scope: {inv.get('scope_selection')}")
    if inv.get("proposals"):
        lines.append("Proposals:")
        for p in inv["proposals"]:
            lines.append(f"  - {p.get('id')}. {p.get('title')}")
    if inv.get("saved_plans"):
        lines.append("Saved plans:")
        for p in inv["saved_plans"]:
            lines.append(f"  - {p.get('id')}. {p.get('title')}")
    if inv.get("plan_aims"):
        lines.append(f"Active plan aims: {', '.join(inv['plan_aims'])}")
    return "\n".join(lines)
