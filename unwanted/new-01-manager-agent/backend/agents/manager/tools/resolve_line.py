import json
import logging

from agents.manager.db import resolve_line_lookup
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


async def tool_resolve_line(state: ManagerState) -> ManagerState:
    logger.debug("tool_resolve_line: starting")
    slots = dict(state.get("slots") or {})
    line = dict(slots.get("line") or {})
    mention = line.get("mention") or ""

    if not mention:
        return {**state, "tool_result": json.dumps({"error": "no_mention"})}

    try:
        match = await resolve_line_lookup(mention, state.get("user_id", ""))
    except Exception as e:
        logger.exception("resolve_line: DB error")
        return {**state, "tool_result": json.dumps({"error": str(e)})}

    result = {}
    if match is None:
        result = {"status": "not_found", "mention": mention}
    elif match.source == "ambiguous":
        result = {"status": "ambiguous", "mention": mention, "candidates": list(match.candidates) if match.candidates else []}
    else:
        line["canonical"] = match.canonical
        line["resolved"] = True
        line["source"] = match.source
        line["candidates"] = []
        result = {"status": "resolved", "canonical": match.canonical, "source": match.source}

        line_slots = list(slots.get("line_slots") or [])
        if not line_slots:
            line_slots = [{"mention": mention, "status": "resolved", "resolved": True, "canonical": match.canonical, "source": match.source, "lookup_locked": True}]
        else:
            for s in line_slots:
                if s.get("mention", "").lower() == mention.lower():
                    s["status"] = "resolved"
                    s["resolved"] = True
                    s["canonical"] = match.canonical
                    s["source"] = match.source
                    s["lookup_locked"] = True
        slots["line"] = line
        slots["line_slots"] = line_slots
        result["line_slots"] = line_slots
        if len(line_slots) == 1 or result.get("canonical"):
            line_slot = line_slots[0] if line_slots else line
            if line_slot.get("status") == "resolved" or line.get("resolved"):
                result["auto_select"] = True
                slots["active_line_index"] = 0 if line_slots else None

    return {
        **state,
        "slots": slots,
        "tool_result": json.dumps(result),
    }
