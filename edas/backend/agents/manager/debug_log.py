import json
from typing import Any

from config import get_settings


def debug(node: str, message: str, **fields: Any) -> None:
    if not get_settings().debug:
        return
    if fields:
        print(f"[DEBUG][{node}] {message} {json.dumps(fields, default=str)}")
    else:
        print(f"[DEBUG][{node}] {message}")


def debug_route(node: str, target: str) -> None:
    debug(node, f"-> {target}")


def debug_state(node: str, state: dict) -> None:
    if not get_settings().debug:
        return
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    time_slot = slots.get("time") or {}
    aim = slots.get("aim") or {}
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
