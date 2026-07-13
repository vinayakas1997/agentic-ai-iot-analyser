import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


async def tool_generate_plans(state: ManagerState) -> ManagerState:
    logger.debug("tool_generate_plans: starting")
    slots = state.get("slots") or {}
    line_context = state.get("line_context") or {}
    aim = slots.get("aim") or {}
    time_slot = slots.get("time") or {}
    line = slots.get("line") or {}

    context_inventory = json.dumps(line_context.get("dataset_summaries") or [], indent=2)
    datasets_full = json.dumps(line_context.get("datasets_full") or [], indent=2)
    join_catalog = json.dumps(line_context.get("join_catalog") or [], indent=2)
    suggested = json.dumps(line_context.get("suggested_aims") or [])

    system = load_prompt(
        "propose_analysis_plans",
        scope_label=line.get("canonical") or "",
        session_goal=state.get("session_goal") or "",
        user_explore_intent=state.get("user_explore_intent") or "",
        context_inventory=context_inventory,
        datasets_full=datasets_full,
        join_catalog=join_catalog,
        registry_suggested_aims=suggested,
        saved_plans_json=json.dumps(state.get("saved_plans") or []),
        existing_proposals_json=json.dumps(state.get("analysis_proposals") or []),
        seen_proposal_titles_json=json.dumps(state.get("seen_proposal_titles") or []),
        action="propose",
        keep_plan_ids=json.dumps([]),
        change_plan_ids=json.dumps([]),
        change_notes="",
        user_message=state.get("user_message", ""),
    )

    llm = get_llm_client()
    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=state.get("user_message", ""))],
            caller="generate_plans",
        )
    except Exception:
        logger.exception("generate_plans: LLM failed")
        return {**state, "tool_result": json.dumps({"error": "llm_failed"})}

    try:
        parsed = parse_json_from_message(response.content or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}

    proposals = parsed.get("proposals", [])
    normalized = []
    for p in proposals:
        if isinstance(p, dict) and p.get("id") is not None:
            normalized.append({
                "id": int(p["id"]),
                "title": str(p.get("title", "")),
                "aims": p.get("aims", []),
                "what_you_might_see": str(p.get("what_you_might_see", "")),
            })

    seen = set(state.get("seen_proposal_titles") or [])
    for p in normalized:
        seen.add(p["title"])

    all_aims = []
    all_benefits = []
    for p in normalized:
        for a in (p.get("aims") or []):
            if a not in all_aims:
                all_aims.append(a)
        wys = p.get("what_you_might_see", "")
        if wys and wys not in all_benefits:
            all_benefits.append(wys)

    plan = {
        "aims": all_aims,
        "benefits": "\n".join(all_benefits),
        "line": (state.get("slots") or {}).get("line", {}).get("canonical"),
    }

    return {
        **state,
        "plan": plan,
        "analysis_proposals": normalized,
        "seen_proposal_titles": list(seen),
        "explore_phase": "proposing",
        "phase": "ask",
        "tool_result": json.dumps({"proposals": normalized, "plan": plan}),
    }
