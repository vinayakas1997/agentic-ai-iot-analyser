import json
from typing import Any

from config import get_settings

from harness.tracer import record as _trace_record


def debug(node: str, message: str, **fields: Any) -> None:
    _trace_record("debug", node, message=message, fields=fields)
    if not get_settings().debug:
        return
    if fields:
        print(f"[DEBUG][{node}] {message} {json.dumps(fields, default=str)}")
    else:
        print(f"[DEBUG][{node}] {message}")


def debug_route(node: str, target: str) -> None:
    _trace_record("routing", node, target=target)
    debug(node, f"-> {target}")


def debug_state(node: str, state: dict) -> None:
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    time_slot = slots.get("time") or {}
    aim = slots.get("aim") or {}
    _trace_record(
        "node_state",
        node,
        phase=state.get("phase"),
        missing=state.get("missing"),
        error=state.get("error"),
        line_mention=line.get("mention"),
        line_canonical=line.get("canonical"),
        line_source=line.get("source"),
        time_raw=time_slot.get("raw"),
        time_start=time_slot.get("start"),
        time_end=time_slot.get("end"),
        time_resolved=time_slot.get("resolved"),
        time_ambiguous=time_slot.get("ambiguous"),
        aim_raw=aim.get("raw"),
        registry_sync_target=state.get("registry_sync_target"),
    )
    if not get_settings().debug:
        return
    debug(
        node,
        "state",
        phase=state.get("phase"),
        missing=state.get("missing"),
        error=state.get("error"),
        line_mention=line.get("mention"),
        line_canonical=line.get("canonical"),
        line_source=line.get("source"),
        time_raw=time_slot.get("raw"),
        time_start=time_slot.get("start"),
        time_end=time_slot.get("end"),
        time_resolved=time_slot.get("resolved"),
        aim_raw=aim.get("raw"),
    )
