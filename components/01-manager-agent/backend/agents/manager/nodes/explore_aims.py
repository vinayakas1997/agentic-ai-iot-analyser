import json



from langchain_core.messages import HumanMessage, SystemMessage



from agents.manager.chat_memory import get_recent_chat_messages
from agents.manager.debug_log import debug, debug_state
from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt

from agents.manager.schema_format import (
    explore_context_label,
    format_context_inventory_for_prompt,
    format_datasets_for_prompt,
    format_join_catalog_for_prompt,
)

from agents.manager.slots import compute_missing

from agents.manager.state import ManagerState


def _coerce_aims_list(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    return []


def _normalize_proposals(raw: list) -> list[dict]:

    proposals: list[dict] = []

    for item in raw:

        if not isinstance(item, dict):

            continue

        pid = item.get("id")

        if pid is None:

            continue

        proposals.append(

            {

                "id": int(pid),

                "title": str(item.get("title") or f"Plan {pid}").strip(),

                "aims": _coerce_aims_list(item.get("aims")),

                "what_you_might_see": str(item.get("what_you_might_see") or "").strip(),

                "columns_used": [str(c).strip() for c in (item.get("columns_used") or []) if str(c).strip()],

                "datasets_used": [str(d).strip() for d in (item.get("datasets_used") or []) if str(d).strip()],

                "join_description": str(item.get("join_description") or "").strip(),

                "lines_used": [str(l).strip() for l in (item.get("lines_used") or []) if str(l).strip()],

            }

        )

    proposals.sort(key=lambda p: p["id"])

    return proposals





def _merge_refined_proposals(

    existing: list[dict],

    generated: list[dict],

    keep_plan_ids: list[int],

    change_plan_ids: list[int],

) -> list[dict]:

    by_id = {p["id"]: p for p in existing}

    for p in generated:

        by_id[p["id"]] = p

    merged: list[dict] = []

    for pid in (1, 2, 3):

        if pid in keep_plan_ids and pid in {p["id"] for p in existing}:

            kept = next(p for p in existing if p["id"] == pid)

            merged.append(dict(kept))

        elif pid in change_plan_ids and pid in by_id:

            merged.append(dict(by_id[pid]))

        elif pid in by_id:

            merged.append(dict(by_id[pid]))

        elif pid in {p["id"] for p in existing}:

            kept = next(p for p in existing if p["id"] == pid)

            merged.append(dict(kept))

    if len(merged) < 3:

        for p in generated:

            if p["id"] not in {m["id"] for m in merged}:

                merged.append(dict(p))

    merged.sort(key=lambda p: p["id"])

    return merged[:3]





def format_proposals_message(proposals: list[dict], scope_label: str) -> str:

    lines = [f"Here are 3 analysis options for **{scope_label}**:", ""]

    for p in proposals:

        aims = p.get("aims") or []

        aims_text = "; ".join(aims) if aims else "(no aims)"

        lines.append(f"**{p['id']}. {p.get('title', 'Plan')}**")

        lines.append(f"- **Aims:** {aims_text}")

        if p.get("datasets_used"):

            lines.append(f"- **Datasets:** {', '.join(p['datasets_used'])}")

        if p.get("join_description"):

            lines.append(f"- **Join:** {p['join_description']}")

        if p.get("lines_used"):

            lines.append(f"- **Lines:** {', '.join(p['lines_used'])}")

        if p.get("what_you_might_see"):

            lines.append(f"- **You might see:** {p['what_you_might_see']}")

        lines.append("")

    lines.append(
        'Say **keep plan 2** to save, **more options** for another batch, or **use saved** to list saved plans.'
    )
    return "\n".join(lines)





def _proposal_notes_summary(selected: list[dict]) -> str:

    parts: list[str] = []

    for p in selected:

        detail = [f"Plan {p.get('id')}: {p.get('title', '')}"]

        if p.get("datasets_used"):

            detail.append(f"datasets={', '.join(p['datasets_used'])}")

        if p.get("join_description"):

            detail.append(f"join={p['join_description']}")

        if p.get("lines_used"):

            detail.append(f"lines={', '.join(p['lines_used'])}")

        parts.append("; ".join(detail))

    return " | ".join(parts)





async def propose_or_refine_plans(state: ManagerState) -> ManagerState:

    debug_state("propose_or_refine_plans", state)

    line_context = state.get("line_context") or {}

    explore_context = state.get("explore_context")

    slots = dict(state.get("slots") or {})

    line = slots.get("line") or {}

    canonical = line.get("canonical") or line_context.get("line_name") or "this line"

    scope_label = explore_context_label(explore_context, canonical)

    aim_exploration = state.get("aim_exploration") or {}

    action = aim_exploration.get("action") or "propose"

    existing = list(state.get("analysis_proposals") or [])



    system = load_prompt(

        "propose_analysis_plans",

        scope_label=scope_label,

        context_inventory=format_context_inventory_for_prompt(
            state.get("dataset_context"), slots=slots
        ),

        datasets_full=format_datasets_for_prompt(line_context, explore_context=explore_context),

        join_catalog=format_join_catalog_for_prompt(line_context, explore_context=explore_context),

        registry_suggested_aims=json.dumps(line_context.get("suggested_aims") or []),

        existing_proposals_json=json.dumps(existing, indent=2),

        action=action,

        keep_plan_ids=json.dumps(aim_exploration.get("keep_plan_ids") or []),

        change_plan_ids=json.dumps(aim_exploration.get("change_plan_ids") or []),

        change_notes=aim_exploration.get("change_notes") or "",

        user_message=state.get("user_message") or "",

        user_explore_intent=state.get("user_explore_intent") or "",

        session_goal=state.get("session_goal") or "",

        saved_plans_json=json.dumps(
            [
                {"id": p.get("id"), "title": p.get("title"), "aims": p.get("aims")}
                for p in (state.get("saved_plans") or [])
                if isinstance(p, dict)
            ],
            indent=2,
        ),

    )



    messages = [SystemMessage(content=system)]
    messages.extend(get_recent_chat_messages(state.get("chat_history")))
    messages.append(HumanMessage(content=state.get("user_message") or ""))

    llm = get_llm_client()
    response = await llm.ainvoke(messages, caller="propose_or_refine_plans")

    parsed: dict = {}

    try:

        parsed = parse_json_from_message(response.content or "{}")

    except (json.JSONDecodeError, TypeError):

        parsed = {}



    generated = _normalize_proposals(parsed.get("proposals") or [])

    if action == "refine" and existing:

        proposals = _merge_refined_proposals(

            existing,

            generated,

            aim_exploration.get("keep_plan_ids") or [],

            aim_exploration.get("change_plan_ids") or [],

        )

        explore_phase = "refining"

    else:

        proposals = generated if generated else existing

        explore_phase = "proposing"



    if len(proposals) < 3 and existing:

        proposals = existing



    if not proposals:
        from agents.manager.prompt_hints import TIER2_EXPLORE_NUDGE

        msg = (
            "I couldn't generate analysis options right now. "
            "Try again, or say *what aims can we do* to browse suggested aims."
            f"{TIER2_EXPLORE_NUDGE}"
        )
        debug("propose_or_refine_plans", "empty proposals", action=action)
        return {
            **state,
            "analysis_proposals": None,
            "explore_phase": None,
            "phase": "ask",
            "agent_message": msg,
            "wants_suggested_aims": False,
            "aim_exploration": None,
        }



    debug("propose_or_refine_plans", "done", count=len(proposals), action=action)

    return {

        **state,

        "analysis_proposals": proposals,

        "explore_phase": explore_phase,

        "phase": "explore",

        "agent_message": format_proposals_message(proposals, scope_label),

        "wants_suggested_aims": False,

        "aim_exploration": None,

    }





async def merge_proposals_to_plan(state: ManagerState) -> ManagerState:

    debug_state("merge_proposals_to_plan", state)

    slots = dict(state.get("slots") or {})

    aim = dict(slots.get("aim") or {})

    aim_exploration = state.get("aim_exploration") or {}

    proposals = list(state.get("analysis_proposals") or [])

    line = slots.get("line") or {}

    time_slot = dict(slots.get("time") or {})

    explore_context = state.get("explore_context")



    selected_ids = aim_exploration.get("selected_plan_ids") or []

    if not selected_ids:

        selected_ids = [p["id"] for p in proposals]



    selected = [p for p in proposals if p.get("id") in selected_ids]

    if not selected:

        selected = proposals



    aims: list[str] = []

    for proposal in selected:

        for aim_text in proposal.get("aims") or []:

            if aim_text not in aims:

                aims.append(aim_text)



    aim["aims"] = aims

    aim["raw"] = "; ".join(aims) if aims else aim.get("raw")

    aim["reorganized"] = True

    slots["aim"] = aim



    notes = _proposal_notes_summary(selected)

    if explore_context and explore_context.get("mode") == "multi_line":

        notes = f"Multi-line exploration. {notes}"



    plan = {

        "line": line.get("canonical"),

        "time_start": time_slot.get("start"),

        "time_end": time_slot.get("end"),

        "aims": aims,

        "alias_name": line.get("canonical"),

        "notes": notes or f"From exploration plans {[p.get('id') for p in selected]}",

    }



    debug("merge_proposals_to_plan", "done", aims=aims, selected=selected_ids)

    return {

        **state,

        "slots": slots,

        "plan": plan,

        "missing": compute_missing(slots),

        "explore_phase": None,

        "phase": "plan",

        "wants_suggested_aims": False,

        "aim_exploration": None,

    }


