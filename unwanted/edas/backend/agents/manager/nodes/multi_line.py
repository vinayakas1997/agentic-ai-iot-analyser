from agents.manager.db import resolve_line_lookup
from agents.manager.message_format import (
    assemble_reply,
    format_web_body_suggested_aims,
)
from agents.manager.prompt_hints import TIER2_EXPLORE_NUDGE, format_aim_missing_hint, format_suggested_aims_block
from agents.manager.schema_format import format_context_inventory_for_prompt
from agents.manager.debug_log import debug, debug_state
from agents.manager.nodes.plan import _format_line_info
from agents.manager.slot_inventory import (
    auto_select_active_line,
    compute_multi_missing,
    format_questions,
    format_slot_summary,
    prepare_questions,
    sync_active_line,
)
from agents.manager.slots import compute_missing
from agents.manager.state import ManagerState


async def resolve_all_lines(state: ManagerState) -> ManagerState:
    debug_state("resolve_all_lines", state)
    slots = dict(state.get("slots") or {})
    line_slots = list(slots.get("line_slots") or [])
    user_id = state.get("user_id", "")

    if not line_slots:
        line = slots.get("line") or {}
        mention = (line.get("mention") or "").strip()
        if mention and not line.get("resolved"):
            from agents.manager.slots import empty_line_slot

            line_slots = [empty_line_slot(mention)]
            slots["line_slots"] = line_slots

    error = None
    for i, slot in enumerate(line_slots):
        if slot.get("lookup_locked") or slot.get("skipped") or slot.get("status") == "resolved":
            continue
        mention = (slot.get("mention") or "").strip()
        if not mention:
            continue

        match = await resolve_line_lookup(mention, user_id)
        if match is None:
            slot["status"] = "not_found"
            slot["resolved"] = False
            slot["canonical"] = None
            slot["source"] = None
            slot["candidates"] = []
            debug("resolve_all_lines", "not_found", mention=mention)
        elif match.source == "ambiguous":
            slot["status"] = "ambiguous"
            slot["resolved"] = False
            slot["canonical"] = None
            slot["source"] = None
            slot["candidates"] = match.candidates
            error = "line_ambiguous"
            debug("resolve_all_lines", "ambiguous", mention=mention, candidates=match.candidates)
        else:
            slot["status"] = "resolved"
            slot["resolved"] = True
            slot["canonical"] = match.canonical
            slot["source"] = match.source
            slot["candidates"] = []
            slot["lookup_locked"] = True
            debug(
                "resolve_all_lines",
                "matched",
                mention=mention,
                canonical=match.canonical,
                source=match.source,
            )
        line_slots[i] = slot

    slots["line_slots"] = line_slots
    slots = auto_select_active_line(slots)

    if len(line_slots) == 1:
        slot = line_slots[0]
        slots["line"] = {
            "mention": slot.get("mention"),
            "canonical": slot.get("canonical"),
            "resolved": slot.get("resolved", False),
            "source": slot.get("source"),
            "candidates": list(slot.get("candidates") or []),
        }
        if slot.get("status") == "not_found":
            error = "line_not_found"
        elif slot.get("status") == "ambiguous":
            error = "line_ambiguous"

    return {
        **state,
        "slots": slots,
        "missing": compute_missing(slots),
        "error": error,
        "phase": "resolve",
    }


async def ask_multi_missing(state: ManagerState) -> ManagerState:
    debug_state("ask_multi_missing", state)
    slots = state.get("slots") or {}
    multi_missing = compute_multi_missing(slots)
    questions = prepare_questions(slots, multi_missing)

    summary = format_slot_summary(slots)
    question_block = format_questions(questions)

    if summary:
        msg = f"{summary}{question_block}"
    elif questions:
        msg = question_block.lstrip()
    else:
        msg = "What would you like to analyze?"

    debug("ask_multi_missing", "reply", questions=[q["id"] for q in questions])
    return {**state, "agent_message": msg, "phase": "ask"}


async def show_suggested_aims(state: ManagerState) -> ManagerState:
    debug_state("show_suggested_aims", state)
    slots = state.get("slots") or {}
    line_context = state.get("line_context") or {}
    line = slots.get("line") or {}
    client = state.get("client") or "cli"
    canonical = line.get("canonical") or line_context.get("line_name") or "this line"
    mention = line.get("mention") or canonical

    suggested = (line_context or {}).get("suggested_aims") or []
    suggested_block = format_suggested_aims_block(suggested)
    next_step = format_aim_missing_hint(canonical) + TIER2_EXPLORE_NUDGE

    if client == "web":
        body = format_web_body_suggested_aims(canonical)
    else:
        inventory = format_context_inventory_for_prompt(
            state.get("dataset_context"), slots=slots
        )
        info = _format_line_info(line_context, slots, brief=False)
        body = (
            f"**Active line:** {canonical} ({mention})\n\n"
            f"**Context:**\n{inventory}\n\n"
            f"{info}\n"
        )
        if suggested_block and suggested_block not in info:
            body += f"\n{suggested_block}\n"

    agent_message, message_next_step = assemble_reply(
        client=client,
        body=body,
        next_step=next_step,
    )
    debug("show_suggested_aims", "reply", line=canonical)
    return {
        **state,
        "agent_message": agent_message,
        "message_next_step": message_next_step,
        "phase": "ask",
        "wants_suggested_aims": False,
    }
