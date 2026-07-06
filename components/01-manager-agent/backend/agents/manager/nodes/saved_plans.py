"""Save, list, combine, and activate saved session plans."""

from agents.manager.debug_log import debug, debug_state
from agents.manager.plan_library import (
    append_saved_plan,
    combine_saved_cards,
    find_saved,
    format_saved_list,
    proposal_to_saved_card,
)
from agents.manager.state import ManagerState


def _plan_from_card(card: dict, slots: dict) -> dict:
    time_slot = slots.get("time") or {}
    line = slots.get("line") or {}
    lines_used = card.get("lines_used") or []
    line_name = lines_used[0] if len(lines_used) == 1 else line.get("canonical")
    return {
        "line": line_name or line.get("canonical"),
        "time_start": time_slot.get("start"),
        "time_end": time_slot.get("end"),
        "aims": list(card.get("aims") or []),
        "alias_name": card.get("title") or line.get("canonical"),
        "notes": card.get("what_you_might_see") or "",
        "benefits": card.get("benefits") or "",
    }


async def save_to_shortlist(state: ManagerState) -> ManagerState:
    debug_state("save_to_shortlist", state)
    aim_exploration = state.get("aim_exploration") or {}
    selected_ids = aim_exploration.get("selected_plan_ids") or []
    proposals = list(state.get("analysis_proposals") or [])
    saved = list(state.get("saved_plans") or [])

    if not selected_ids and proposals:
        selected_ids = [proposals[0].get("id")]

    added: list[str] = []
    errors: list[str] = []
    for pid in selected_ids:
        match = next((p for p in proposals if p.get("id") == pid), None)
        if not match:
            errors.append(f"Plan {pid} not in current batch.")
            continue
        card = proposal_to_saved_card(match)
        saved, err = append_saved_plan(saved, card)
        if err:
            errors.append(err)
            break
        added.append(saved[-1]["id"])

    if added:
        msg = f"Saved **{', '.join(added)}** to your plan list.\n\n{format_saved_list(saved)}"
    elif errors:
        msg = "\n".join(errors)
    else:
        msg = "No plan to save. Run **more options** first, then say **keep plan 2**."

    debug("save_to_shortlist", "done", added=added)
    return {
        **state,
        "saved_plans": saved,
        "agent_message": msg,
        "phase": "ask",
        "aim_exploration": None,
    }


async def list_saved_plans(state: ManagerState) -> ManagerState:
    debug_state("list_saved_plans", state)
    saved = state.get("saved_plans") or []
    return {
        **state,
        "agent_message": format_saved_list(saved),
        "phase": "ask",
        "aim_exploration": None,
    }


async def combine_saved_plans(state: ManagerState) -> ManagerState:
    debug_state("combine_saved_plans", state)
    aim_exploration = state.get("aim_exploration") or {}
    selected = aim_exploration.get("selected_plan_ids") or []
    saved = list(state.get("saved_plans") or [])
    slots = dict(state.get("slots") or {})

    cards = []
    for ref in selected:
        card = find_saved(saved, ref)
        if card:
            cards.append(card)
    if not cards:
        return {
            **state,
            "agent_message": "Could not find saved plans to combine. Say **use saved** to list them.",
            "phase": "ask",
            "aim_exploration": None,
        }

    merged_card = combine_saved_cards(cards)
    plan = _plan_from_card(merged_card, slots)
    aim = dict(slots.get("aim") or {})
    aim["aims"] = plan["aims"]
    aim["raw"] = "; ".join(plan["aims"])
    aim["reorganized"] = True
    slots["aim"] = aim

    debug("combine_saved_plans", "done", aims=plan["aims"])
    return {
        **state,
        "slots": slots,
        "plan": plan,
        "phase": "plan",
        "aim_exploration": None,
    }


async def activate_saved_plan(state: ManagerState) -> ManagerState:
    debug_state("activate_saved_plan", state)
    aim_exploration = state.get("aim_exploration") or {}
    selected = aim_exploration.get("selected_plan_ids") or []
    saved = list(state.get("saved_plans") or [])
    slots = dict(state.get("slots") or {})

    card = None
    for ref in selected:
        card = find_saved(saved, ref)
        if card:
            break
    if not card:
        return {
            **state,
            "agent_message": format_saved_list(saved),
            "phase": "ask",
            "aim_exploration": None,
        }

    plan = _plan_from_card(card, slots)
    aim = dict(slots.get("aim") or {})
    aim["aims"] = plan["aims"]
    aim["raw"] = "; ".join(plan["aims"])
    aim["reorganized"] = True
    slots["aim"] = aim

    return {
        **state,
        "slots": slots,
        "plan": plan,
        "phase": "plan",
        "aim_exploration": None,
    }
