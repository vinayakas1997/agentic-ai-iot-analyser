"""Apply prior task reuse when user references a saved analysis."""

from agents.manager.context.task_history import load_task_history_for_state, resolve_task_alias
from agents.manager.debug_log import debug, debug_state
from agents.manager.slots import compute_missing
from agents.manager.state import ManagerState


async def apply_task_reuse(state: ManagerState) -> ManagerState:
    debug_state("apply_task_reuse", state)
    reuse_alias = state.get("reuse_alias")
    if not reuse_alias:
        return state

    history = await load_task_history_for_state(state)
    entry = resolve_task_alias(reuse_alias, history)
    if not entry:
        debug("apply_task_reuse", "no_match", alias=reuse_alias)
        return state

    slots = dict(state.get("slots") or {})
    aim = dict(slots.get("aim") or {})
    aims = entry.get("aims") or []
    if aims:
        aim["aims"] = list(aims)
        aim["raw"] = "; ".join(aims)
        aim["reorganized"] = True
        slots["aim"] = aim

    time_range = entry.get("time_range")
    if time_range and isinstance(time_range, dict):
        time_slot = dict(slots.get("time") or {})
        time_slot["start"] = time_range.get("start")
        time_slot["end"] = time_range.get("end")
        time_slot["resolved"] = True
        time_slot["no_filter"] = not time_range.get("start") and not time_range.get("end")
        time_slot["mentioned"] = True
        slots["time"] = time_slot

    ds_in_scope = entry.get("datasets_in_scope") or []
    if ds_in_scope:
        dc = dict(slots.get("dataset_context") or state.get("dataset_context") or {})
        active = (slots.get("line") or {}).get("canonical")
        if active:
            by_line = dict(dc.get("by_line") or {})
            line_ctx = dict(by_line.get(active) or {})
            line_ctx["included"] = list(ds_in_scope)
            by_line[active] = line_ctx
            dc["by_line"] = by_line
            dc["included"] = list(ds_in_scope)
            slots["dataset_context"] = dc

    debug("apply_task_reuse", "applied", version=entry.get("version"), aims=len(aims))
    return {
        **state,
        "slots": slots,
        "missing": compute_missing(slots),
        "reuse_alias": None,
        "registry_sync_target": "reorganize",
    }
