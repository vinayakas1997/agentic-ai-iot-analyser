import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


async def tool_resolve_time(state: ManagerState) -> ManagerState:
    logger.debug("tool_resolve_time: starting")
    slots = dict(state.get("slots") or {})
    time_slot = dict(slots.get("time") or {})
    raw = (time_slot.get("raw") or "").strip()
    reference_now = state.get("reference_now", "")

    if not raw:
        time_slot["resolved"] = True
        time_slot["no_filter"] = True
        slots["time"] = time_slot
        return {
            **state,
            "slots": slots,
            "tool_result": json.dumps({"status": "no_filter"}),
        }

    system = load_prompt(
        "normalize_time",
        reference_now=reference_now,
        time_raw=raw,
        validation_error_block="",
    )

    llm = get_llm_client()
    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=raw)],
            caller="resolve_time",
        )
    except Exception:
        logger.exception("resolve_time: LLM failed")
        return {**state, "tool_result": json.dumps({"error": "llm_failed"})}

    try:
        result = parse_json_from_message(response.content or "{}")
    except (json.JSONDecodeError, TypeError):
        result = {"kind": "invalid", "reason": "LLM returned malformed JSON"}

    kind = result.get("kind")

    if kind == "ambiguous":
        time_slot["ambiguous"] = True
        time_slot["interpretations"] = result.get("interpretations", [])
        time_slot["resolved"] = False
    elif kind == "invalid":
        time_slot["parse_error"] = result.get("reason", "invalid time phrase")
        time_slot["resolved"] = False
    elif kind == "relative":
        time_slot["canonical"] = result.get("canonical")
        time_slot["resolved"] = True
        time_slot["ambiguous"] = False
    elif kind == "absolute":
        time_slot["start"] = result.get("start")
        time_slot["end"] = result.get("end")
        time_slot["canonical"] = result.get("canonical") or f"{result.get('start')} to {result.get('end')}"
        time_slot["resolved"] = True
        time_slot["ambiguous"] = False

    slots["time"] = time_slot

    return {
        **state,
        "slots": slots,
        "tool_result": json.dumps(result),
    }
