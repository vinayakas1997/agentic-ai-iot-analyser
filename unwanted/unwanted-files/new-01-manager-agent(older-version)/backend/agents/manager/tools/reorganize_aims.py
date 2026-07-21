import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


async def tool_reorganize_aims(state: ManagerState) -> ManagerState:
    logger.debug("tool_reorganize_aims: starting")
    slots = state.get("slots") or {}
    line_context = state.get("line_context") or {}
    aim = slots.get("aim") or {}
    time_slot = slots.get("time") or {}
    line = slots.get("line") or {}

    time_json = json.dumps({"start": time_slot.get("start"), "end": time_slot.get("end"), "raw": time_slot.get("raw")})
    suggested = json.dumps(line_context.get("suggested_aims") or [])
    datasets_summary = json.dumps(line_context.get("dataset_summaries") or [], indent=2)
    datasets_full = json.dumps(line_context.get("datasets_full") or [], indent=2)

    system = load_prompt(
        "reorganize_aim",
        canonical_line_name=line.get("canonical") or "",
        scope_label=line.get("canonical") or "",
        context_inventory=datasets_summary,
        datasets_full=datasets_full,
        join_catalog=json.dumps(line_context.get("join_catalog") or []),
        suggested_aims=suggested,
        aim_raw=aim.get("raw") or "",
        time_json=time_json,
    )

    llm = get_llm_client()
    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=aim.get("raw") or "")],
            caller="reorganize_aims",
        )
    except Exception:
        logger.exception("reorganize_aims: LLM failed")
        return {**state, "tool_result": json.dumps({"error": "llm_failed"})}

    try:
        parsed = parse_json_from_message(response.content or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}

    raw_aims = parsed.get("aims")
    if isinstance(raw_aims, list):
        aim["aims"] = [str(a).strip() for a in raw_aims if str(a).strip()]
    elif aim.get("raw"):
        aim["aims"] = [aim["raw"]]
    aim["reorganized"] = True

    slots["aim"] = aim

    plan = {
        "line": line.get("canonical"),
        "time_start": time_slot.get("start"),
        "time_end": time_slot.get("end"),
        "aims": aim["aims"],
        "alias_name": parsed.get("alias_name") or line.get("canonical"),
        "notes": parsed.get("notes"),
    }

    return {
        **state,
        "slots": slots,
        "plan": plan,
        "analysis_proposals": None,
        "phase": "ask",
        "tool_result": json.dumps({"aims": aim["aims"], "plan": plan}),
    }
