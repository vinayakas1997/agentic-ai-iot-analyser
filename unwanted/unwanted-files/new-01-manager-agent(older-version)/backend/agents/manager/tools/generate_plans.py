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

    selected_aim = _match_registry_suggested_aim(
        state.get("user_message"), line_context.get("suggested_aims")
    )
    if not selected_aim:
        selected_aim = state.get("selected_suggested_aim")

    user_message = state.get("user_message", "")
    action = "propose"
    if selected_aim:
        user_message = selected_aim
        action = "propose_focused"

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
        action=action,
        keep_plan_ids=json.dumps([]),
        change_plan_ids=json.dumps([]),
        change_notes="",
        user_message=user_message,
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
                "datasets_used": p.get("datasets_used", []),
                "columns_used": p.get("columns_used", []),
                "join_description": p.get("join_description", ""),
            })

    logger.info("generate_plans: parsed=%d proposals, normalized=%d, raw=%s",
                 len(proposals), len(normalized),
                 json.dumps(parsed, indent=2)[:800])

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
    # selected_aim already computed above from user_message + selected_suggested_aim
    if selected_aim:
        selected_norm = selected_aim.strip().lower()
        # Try exact textual match first (aims + title)
        focused = [
            p for p in normalized
            if any(
                selected_norm in a.lower() or a.lower() in selected_norm
                for a in (p.get("aims") or [])
                if a
            ) or selected_norm in (p.get("title") or "").lower()
        ]
        logger.info("generate_plans: selected_aim=%r normalized=%d focused=%d",
                     selected_aim, len(normalized), len(focused))
        if not focused and len(normalized) == 1:
            logger.info("generate_plans: single proposal fallback — keeping LLM proposal")
            focused = normalized
        # If still no match but we have proposals, pick the one with most
        # word overlap — the LLM often rephrases the registry aim creatively.
        if not focused and normalized:
            def _score(p):
                text = (p.get("title") or "") + " " + " ".join(p.get("aims") or [])
                return sum(1 for w in selected_norm.split() if len(w) > 2 and w in text.lower())
            best = max(normalized, key=_score)
            logger.info("generate_plans: word-overlap fallback — picked title=%r score=%d",
                         best.get("title"), _score(best))
            focused = [best]
        if not focused:
            logger.info("generate_plans: PLACEHOLDER used — no proposals from LLM")
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

    # For focused proposals from a registry suggested aim, override title and
    # aims with the original registry text. The LLM rephrases these which
    # breaks provenance matching and shows inconsistent titles to the user.
    if selected_aim and len(normalized) == 1:
        normalized[0]["title"] = selected_aim
        normalized[0]["aims"] = [selected_aim]

    # If user selected a registry suggested aim, always override datasets_used /
    # columns_used from the registry — the LLM sometimes invents column names
    # or omits them, while the registry data is authoritative.
    if selected_aim:
        for s_aim in (line_context.get("suggested_aims") or []):
            reg_text = s_aim if isinstance(s_aim, str) else (s_aim.get("aim") if isinstance(s_aim, dict) else "")
            if reg_text and reg_text.strip().lower() == selected_aim.strip().lower():
                reg_columns = s_aim.get("columns") if isinstance(s_aim, dict) else None
                if reg_columns:
                    for p in normalized:
                        p["datasets_used"] = [c["dataset"] for c in reg_columns]
                        p["columns_used"] = list(dict.fromkeys(
                            col_name for c in reg_columns for col_name in c.get("names", [])
                        ))
                        if len(reg_columns) > 1:
                            ds_names = [c["dataset"] for c in reg_columns]
                            p["join_description"] = f"{' ↔ '.join(ds_names)}"
                break

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

    for i, p in enumerate(normalized):
        if not p.get("display_number"):
            p["display_number"] = i + 1
        p["confirm_id"] = f"pro-{i + 1}"

    if len(normalized) == 1:
        p = normalized[0]
        title = p.get("title", "")
        feasible = p.get("feasible", True)
        feasibility_tag = "(Doable)" if feasible else "(Not doable)"
        agent_message = f"Plan ready: **{title}** {feasibility_tag} — see the card below for details."
    else:
        proposal_msgs = []
        for p in normalized:
            aims_str = "; ".join(p.get("aims") or [])
            dn = p.get("display_number", 0)
            proposal_msgs.append(f"  * Option {dn} — {p['title']}: {aims_str}")
        proposals_text = "\n".join(proposal_msgs)
        first_dn = normalized[0].get("display_number", 1)
        last_dn = normalized[-1].get("display_number", len(normalized))
        agent_message = (
            f"I generated {len(normalized)} analysis options:\n\n{proposals_text}\n\n"
            f"Pick one by replying **confirm {first_dn}**, **confirm {first_dn + 1}**, etc. to narrow down, "
            "or ask **more options** for fresh alternatives."
        )

    return {
        **state,
        "plan": plan,
        "analysis_proposals": normalized,
        "selected_proposal_index": None,
        "proposal_counter": len(normalized),
        "seen_proposal_titles": list(seen),
        "explore_phase": "proposing",
        "phase": "ask",
        "agent_message": agent_message,
        "tool_result": json.dumps({"proposals": normalized, "plan": plan}),
    }
