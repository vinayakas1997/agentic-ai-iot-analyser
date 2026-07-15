import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


def _match_registry_suggested_aim(user_message: str, suggested_aims: list) -> str | None:
    """Does the user's current message clearly refer to one registry-suggested aim?

    Computed fresh from state.user_message + line_context every call, rather
    than a flag set by an earlier node and carried across turns/nodes — that
    approach proved unreliable (the session's checkpoint resume could
    resurrect a stale value from an earlier point in a prior turn, causing
    e.g. "more options" to incorrectly stay pinned to the previously
    selected aim). user_message and line_context are both freshly
    reconstructed every turn, so this is safe to recompute each time.
    """
    user_norm = (user_message or "").strip().lower()
    if not user_norm:
        return None
    for s_aim in suggested_aims or []:
        aim_text = s_aim if isinstance(s_aim, str) else (s_aim.get("aim") if isinstance(s_aim, dict) else None)
        if not aim_text:
            continue
        aim_norm = aim_text.strip().lower()
        if aim_norm == user_norm or user_norm in aim_norm or aim_norm in user_norm:
            return aim_text
    return None


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
                "feasible": p.get("feasible", True),
                "feasibility_reason": p.get("feasibility_reason", ""),
                "alternative": p.get("alternative", ""),
            })

    seen = set(state.get("seen_proposal_titles") or [])
    for p in normalized:
        seen.add(p["title"])

    # If user selected a suggested aim, keep only the focused proposal.
    # Match fuzzily against each proposal's aim text — the LLM's proposals
    # are usually a longer rewrite of the short registry aim ("Calculate
    # average defect rate by batch for the FRUITS_TEST line using the
    # fruit_quality dataset." vs "average defect rate by batch"), so exact
    # list membership almost never hits and we'd fall through to the generic
    # placeholder below, losing the LLM's actual benefits/what_you_might_see
    # text.
    selected_aim = _match_registry_suggested_aim(
        state.get("user_message"), line_context.get("suggested_aims")
    )
    if selected_aim:
        selected_norm = selected_aim.strip().lower()
        focused = [
            p for p in normalized
            if any(
                selected_norm in a.lower() or a.lower() in selected_norm
                for a in (p.get("aims") or [])
                if a
            )
        ]
        if not focused and len(normalized) == 1:
            # The model already narrowed to a single proposal on its own
            # (per the prompt's "user selected a specific aim" rule) — even
            # if its phrasing doesn't textually match the registry aim, it's
            # the only candidate, so keep its real title/benefits instead of
            # discarding them for the generic placeholder below.
            focused = normalized
        if not focused:
            focused = [{
                "id": 1,
                "title": selected_aim,
                "aims": [selected_aim],
                "what_you_might_see": "This analysis focuses on " + selected_aim,
                "feasible": True,
                "feasibility_reason": "",
                "alternative": "",
            }]
        normalized = focused
    elif len(normalized) > 1:
        # No registry-suggested-aim match, but the model still returned (or
        # reused) more than one proposal. If the user's current aim text
        # clearly points at only some of them, don't silently fold every
        # proposal's aims into the plan — that resurrects stale/unrelated
        # proposals from earlier in the session.
        aim_raw = (aim.get("raw") or state.get("user_message") or "").strip().lower()
        if aim_raw:
            focused = [
                p for p in normalized
                if any(
                    aim_raw in a.lower() or a.lower() in aim_raw
                    for a in (p.get("aims") or [])
                    if a
                )
            ]
            if focused and len(focused) < len(normalized):
                normalized = focused

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

    proposal_msgs = []
    for p in normalized:
        aims_str = "; ".join(p.get("aims") or [])
        proposal_msgs.append(f"  * {p['title']}: {aims_str}")
    proposals_text = "\n".join(proposal_msgs)
    if len(normalized) == 1:
        agent_message = (
            f"I found a focused analysis plan for you:\n\n{proposals_text}\n\n"
            "Review it above, then reply **confirm 1** to lock it in and see the review card, "
            "or **more options** to explore fresh alternatives."
        )
    else:
        agent_message = (
            f"I generated {len(normalized)} analysis options:\n\n{proposals_text}\n\n"
            "Pick one by replying **confirm 1**, **confirm 2**, etc. to narrow down, "
            "or ask **more options** for fresh alternatives."
        )

    return {
        **state,
        "plan": plan,
        "analysis_proposals": normalized,
        "seen_proposal_titles": list(seen),
        "explore_phase": "proposing",
        "phase": "ask",
        "agent_message": agent_message,
        "tool_result": json.dumps({"proposals": normalized, "plan": plan}),
    }
