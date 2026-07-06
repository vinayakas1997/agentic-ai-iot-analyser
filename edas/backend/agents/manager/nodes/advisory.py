import json

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.debug_log import debug, debug_state
from agents.manager.nodes.extract import _get_llm
from agents.manager.prompt_hints import format_advisory_footer
from agents.manager.prompts import load_prompt
from agents.manager.schema_format import (
    explore_context_label,
    format_context_inventory_for_prompt,
    format_datasets_for_prompt,
)
from agents.manager.state import ManagerState


def _proposals_summary(proposals: list[dict] | None) -> str:
    summary = []
    for p in proposals or []:
        if not isinstance(p, dict):
            continue
        summary.append(
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "aims": p.get("aims"),
                "what_you_might_see": p.get("what_you_might_see"),
            }
        )
    return json.dumps(summary, indent=2) if summary else "[]"


async def answer_advisory(state: ManagerState) -> ManagerState:
    debug_state("answer_advisory", state)
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    line_context = state.get("line_context") or {}
    explore_context = state.get("explore_context")
    canonical = line.get("canonical") or line_context.get("line_name") or "this line"
    scope_label = explore_context_label(
        explore_context,
        canonical,
    )
    plan = state.get("plan") or {}
    plan_aims = plan.get("aims") or (slots.get("aim") or {}).get("aims") or []
    suggested = line_context.get("suggested_aims") or []
    has_plan = bool(plan_aims)

    system = load_prompt(
        "advisory_answer",
        canonical_line_name=canonical,
        scope_label=scope_label,
        phase=state.get("phase") or "ask",
        has_plan="yes" if has_plan else "no",
        context_inventory=format_context_inventory_for_prompt(
            state.get("dataset_context"), slots=slots
        ),
        datasets_full=format_datasets_for_prompt(line_context, explore_context=explore_context),
        suggested_aims=json.dumps(suggested),
        proposals_json=_proposals_summary(state.get("analysis_proposals")),
        plan_aims_json=json.dumps(plan_aims),
        user_message=state.get("user_message") or "",
    )
    llm = _get_llm()
    response = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=state.get("user_message") or "")]
    )
    body = (response.content or "").strip()
    footer = format_advisory_footer(plan if has_plan else None, canonical)
    msg = f"{body}\n\n{footer}" if body else footer
    debug("answer_advisory", "reply", line=canonical, chars=len(body))

    wishes = list(state.get("iot_column_wishes") or [])
    user_msg = (state.get("user_message") or "").lower()
    if any(k in user_msg for k in ("new column", "columns required", "more columns", "additional column")):
        for token in ("temperature", "sensor", "humidity", "pressure"):
            if token in user_msg and not any((w.get("name") or "").lower() == token for w in wishes):
                wishes.append({"name": token, "source": "advisory"})

    return {
        **state,
        "agent_message": msg,
        "phase": "ask",
        "iot_column_wishes": wishes,
    }
