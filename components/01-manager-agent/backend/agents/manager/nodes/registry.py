from agents.manager.debug_log import debug, debug_state
from agents.manager.registry_context import sync_dataset_context_for_state
from agents.manager.slots import compute_missing
from agents.manager.state import ManagerState


def _resolved_line_slots(slots: dict) -> list[dict]:
    return [
        s
        for s in slots.get("line_slots") or []
        if s.get("status") == "resolved" and not s.get("skipped") and s.get("canonical")
    ]


async def sync_registry_context(state: ManagerState) -> ManagerState:
    """Fetch/cache line bundles, apply dataset include/exclude policy, build line_context."""
    debug_state("sync_registry_context", state)
    slots = dict(state.get("slots") or {})
    resolved = _resolved_line_slots(slots)
    if not resolved:
        return {**state, "phase": "context", "missing": compute_missing(slots)}

    dataset_context, line_context, explore_context, error_info = await sync_dataset_context_for_state(
        slots,
        slots.get("dataset_context") or state.get("dataset_context"),
    )

    if error_info and error_info.get("error") == "no_datasets":
        line = error_info.get("line") or "unknown"
        return {
            **state,
            "dataset_context": dataset_context,
            "error": "no_datasets",
            "agent_message": (
                f"**{line}** is registered but has no active datasets.\n\n"
                "Please contact the IoT team."
            ),
            "phase": "ask",
        }

    slots_with_ctx = {**slots, "dataset_context": dataset_context}
    debug(
        "sync_registry_context",
        "done",
        lines=list((dataset_context.get("by_line") or {}).keys()),
        active=dataset_context.get("active_line"),
    )
    return {
        **state,
        "slots": slots_with_ctx,
        "dataset_context": dataset_context,
        "line_context": line_context,
        "explore_context": explore_context,
        "missing": compute_missing(slots_with_ctx),
        "phase": "context",
        "registry_sync_target": state.get("registry_sync_target"),
    }


async def line_not_found(state: ManagerState) -> ManagerState:
    mention = (state.get("slots") or {}).get("line", {}).get("mention") or "that line"
    debug("line_not_found", "reply", mention=mention)
    return {
        **state,
        "agent_message": (
            f"I couldn't find **{mention}** in the IoT catalog.\n\n"
            "This line may have been removed or is not registered yet. "
            "Please contact the IoT team or try another name."
        ),
        "phase": "ask",
    }
