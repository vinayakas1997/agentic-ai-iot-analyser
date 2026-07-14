import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


async def tool_answer_advisory(state: ManagerState) -> ManagerState:
    logger.debug("tool_answer_advisory: starting")
    slots = state.get("slots") or {}
    line_context = state.get("line_context") or {}
    line = slots.get("line") or {}
    plan = state.get("plan")

    context_inventory = json.dumps(line_context.get("dataset_summaries") or [], indent=2)
    datasets_full = json.dumps(line_context.get("datasets_full") or [], indent=2)
    suggested = json.dumps(line_context.get("suggested_aims") or [])

    system = load_prompt(
        "advisory_answer",
        canonical_line_name=line.get("canonical") or "",
        scope_label=line.get("canonical") or "",
        phase=state.get("phase", ""),
        has_plan=str(bool(plan)).lower(),
        context_inventory=context_inventory,
        datasets_full=datasets_full,
        suggested_aims=suggested,
        proposals_json=json.dumps(state.get("analysis_proposals") or []),
        plan_aims_json=json.dumps(plan.get("aims") if plan else []),
        user_message=state.get("user_message", ""),
        line_mention=line.get("mention") or "",
        line_source=line.get("source") or "",
    )

    llm = get_llm_client()
    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=state.get("user_message", ""))],
            caller="answer_advisory",
        )
    except Exception:
        logger.exception("answer_advisory: LLM failed")
        return {**state, "tool_result": json.dumps({"error": "llm_failed"})}

    message = (response.content or "").strip()

    return {
        **state,
        "agent_message": message,
        "phase": "ask",
        "tool_result": json.dumps({"message": message}),
    }
