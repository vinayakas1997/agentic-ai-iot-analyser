"""Session Inventory facade — unified read model for prompts and meta answers."""

from __future__ import annotations

from agents.manager.context.join import build_join_inventory, format_join_for_prompt
from agents.manager.context.plan_explore import (
    build_plan_explore_inventory,
    format_plan_explore_for_prompt,
)
from agents.manager.context.scope import build_scope_inventory, format_scope_for_prompt
from agents.manager.context.task_history import build_task_history_inventory
from agents.manager.context.time import build_time_inventory, format_time_for_prompt
from agents.manager.context.verification import build_verification_inventory, format_verification_for_prompt
from agents.manager.registry_context import build_context_inventory


def build_session_inventory(
    state: dict,
    *,
    task_history: list[dict] | None = None,
) -> dict:
    slots = state.get("slots") or {}
    dataset_context = state.get("dataset_context") or slots.get("dataset_context")
    registry = build_context_inventory(dataset_context, slots=slots)
    time_inv = build_time_inventory(slots)
    scope_inv = build_scope_inventory(slots)
    plan_inv = build_plan_explore_inventory(state)
    join_inv = build_join_inventory(state.get("line_context"))
    verify_inv = build_verification_inventory(state.get("verification_context"))
    task_inv = build_task_history_inventory(state, task_history)

    return {
        "phase": state.get("phase"),
        "missing": list(state.get("missing") or []),
        "registry": registry,
        "time": time_inv,
        "scope": scope_inv,
        "plan_explore": plan_inv,
        "join": join_inv,
        "verification": verify_inv,
        "task_history": task_inv,
    }


def format_session_inventory_for_prompt(state: dict, *, max_lines: int = 20) -> str:
    inv = state.get("session_inventory") or build_session_inventory(state)
    blocks: list[str] = []

    phase = inv.get("phase") or "?"
    missing = inv.get("missing") or []
    blocks.append(f"Phase: {phase}; missing: {', '.join(missing) if missing else 'none'}")

    registry = inv.get("registry") or {}
    for line_info in registry.get("lines") or []:
        name = line_info.get("line_name")
        inc = ", ".join(line_info.get("included_datasets") or []) or "all"
        blocks.append(f"Line **{name}**: in scope [{inc}]")

    blocks.append(format_time_for_prompt(inv.get("time")))
    blocks.append(format_scope_for_prompt(inv.get("scope")))
    blocks.append(format_plan_explore_for_prompt(inv.get("plan_explore")))

    join_text = format_join_for_prompt(inv.get("join"))
    if join_text and "none known" not in join_text:
        blocks.append(join_text)

    verify = inv.get("verification") or {}
    if verify.get("checked"):
        blocks.append(format_verification_for_prompt(verify))

    return "\n".join(blocks[:max_lines])
