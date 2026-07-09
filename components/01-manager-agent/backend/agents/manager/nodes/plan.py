import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from api.websocket import broadcast_event

from agents.manager.db import save_task_definition
from agents.manager.debug_log import debug, debug_state
from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.nodes.explore_aims import _coerce_aims_list
from agents.manager.session_db import update_session_mode
from agents.manager.message_format import (
    assemble_reply,
    format_line_info_cli,
    format_line_match_note,
    format_web_body_after_line_resolve,
)
from agents.manager.prompt_hints import format_ask_for_missing
from agents.manager.prompts import load_prompt
from agents.manager.registry_context import build_planner_schema_payload
from agents.manager.schema_format import (
    explore_context_label,
    format_context_inventory_for_prompt,
    format_datasets_for_prompt,
    format_join_catalog_for_prompt,
    format_join_catalog_user_block,
    format_multi_dataset_columns_user_block,
)
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)

_CONFIRM_WORDS = ("go", "confirm", "yes", "proceed", "ok")


def _format_line_info(line_context: dict | None, slots: dict | None = None, *, brief: bool = False) -> str:
    return format_line_info_cli(line_context, slots, brief=brief)


def _ask_for(missing: list[str], slots: dict | None = None) -> str:
    return format_ask_for_missing(missing, slots)


def _plan_time_line(time_slot: dict) -> str:
    if time_slot.get("no_filter"):
        return "all data (no date filter)"
    if time_slot.get("resolved") and time_slot.get("start") and time_slot.get("end"):
        raw = time_slot.get("raw") or ""
        note = f' (from "{raw}")' if raw else ""
        return f"{time_slot['start']} → {time_slot['end']}{note}"
    return "all data (no date filter)"


async def ask_line_ambiguous(state: ManagerState) -> ManagerState:
    debug_state("ask_line_ambiguous", state)
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    mention = line.get("mention") or "that name"
    candidates = line.get("candidates") or []
    listed = ", ".join(f"**{c}**" for c in candidates)
    msg = (
        f'Multiple lines match **"{mention}"**: {listed}.\n\n'
        "Please reply with the exact line name you want."
    )
    debug("ask_line_ambiguous", "reply", candidates=candidates)
    return {**state, "agent_message": msg, "phase": "ask"}


async def ask_time_ambiguous(state: ManagerState) -> ManagerState:
    debug_state("ask_time_ambiguous", state)
    slots = state.get("slots") or {}
    time_slot = slots.get("time") or {}
    raw = time_slot.get("raw") or "that phrase"
    if time_slot.get("ambiguous"):
        interpretations = time_slot.get("interpretations") or []
        listed = "\n".join(f"  - {item}" for item in interpretations)
        msg = (
            f'Time phrase **"{raw}"** is unclear. Did you mean:\n{listed}\n\n'
            "Please reply with one."
        )
    else:
        detail = time_slot.get("parse_error") or "could not parse time"
        msg = (
            f'Could not understand time phrase **"{raw}"**: {detail}\n\n'
            "Please rephrase the time range."
        )
    debug("ask_time_ambiguous", "reply", raw=raw)
    return {**state, "agent_message": msg, "phase": "ask"}


async def ask_missing(state: ManagerState) -> ManagerState:
    debug_state("ask_missing", state)
    missing = state.get("missing") or []
    slots = state.get("slots") or {}
    line_context = state.get("line_context")
    client = state.get("client") or "cli"
    brief = "line" not in missing and line_context is not None
    next_step = _ask_for(missing, slots) or "What would you like to analyze?"

    if client == "web" and line_context is not None and "line" not in missing:
        if format_line_match_note(slots):
            body = format_web_body_after_line_resolve(slots, line_context)
        elif "aim" in missing and len(missing) == 1:
            body = ""
        else:
            body = format_web_body_after_line_resolve(slots, line_context)
    else:
        info = _format_line_info(line_context, slots, brief=brief)
        body = f"I found the following:\n\n{info}" if info else ""

    if not body:
        agent_message = next_step
        message_next_step = None
    else:
        agent_message, message_next_step = assemble_reply(
            client=client,
            body=body,
            next_step=next_step,
        )

    debug("ask_missing", "reply", missing=missing)
    return {
        **state,
        "agent_message": agent_message,
        "message_next_step": message_next_step,
        "phase": "ask",
    }


async def reorganize_aim(state: ManagerState) -> ManagerState:
    debug_state("reorganize_aim", state)
    state = {**state, "error": None}
    slots = state.get("slots") or {}
    line_context = state.get("line_context") or {}
    aim = slots.get("aim") or {}
    time_slot = slots.get("time") or {}

    datasets_summary = json.dumps(line_context.get("dataset_summaries") or [], indent=2)
    suggested = json.dumps(line_context.get("suggested_aims") or [])
    explore_context = state.get("explore_context")
    datasets_full = format_datasets_for_prompt(line_context, explore_context=explore_context)
    join_catalog = format_join_catalog_for_prompt(line_context, explore_context=explore_context)
    context_inventory = format_context_inventory_for_prompt(
        state.get("dataset_context"), slots=slots
    )
    scope_label = explore_context_label(
        explore_context,
        (slots.get("line") or {}).get("canonical") or "",
    )
    time_json = json.dumps(
        {"start": time_slot.get("start"), "end": time_slot.get("end"), "raw": time_slot.get("raw")}
    )

    system = load_prompt(
        "reorganize_aim",
        canonical_line_name=(slots.get("line") or {}).get("canonical") or "",
        scope_label=scope_label,
        context_inventory=context_inventory,
        datasets_full=datasets_full,
        join_catalog=join_catalog,
        suggested_aims=suggested,
        aim_raw=aim.get("raw") or "",
        time_json=time_json,
    )
    llm = get_llm_client()
    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=aim.get("raw") or "")],
            caller="reorganize_aim",
        )
    except Exception:
        logger.exception("reorganize_aim: LLM call failed")
        return {**state, "error": "llm_failed", "agent_message": "I couldn't reorganize the plan. Please try again.", "phase": "ask"}
    parsed: dict = {}
    try:
        parsed = parse_json_from_message(response.content or "{}")
        raw_aims = parsed.get("aims")
        if raw_aims is None and aim.get("raw"):
            raw_aims = [aim.get("raw")]
        aims = _coerce_aims_list(raw_aims)
    except (json.JSONDecodeError, TypeError):
        aims = _coerce_aims_list(aim.get("raw"))

    aim["aims"] = aims
    aim["reorganized"] = True
    slots["aim"] = aim

    plan = {
        "line": (slots.get("line") or {}).get("canonical"),
        "time_start": time_slot.get("start"),
        "time_end": time_slot.get("end"),
        "aims": aim["aims"],
        "alias_name": parsed.get("alias_name") or (slots.get("line") or {}).get("canonical"),
        "notes": parsed.get("notes"),
    }
    debug("reorganize_aim", "done", aims=aim["aims"])
    return {
        **state,
        "slots": slots,
        "plan": plan,
        "phase": "plan",
        "registry_sync_target": None,
    }


async def _generate_plan_benefits(state: ManagerState, plan: dict) -> str:
    slots = state.get("slots") or {}
    line_context = state.get("line_context") or {}
    explore_context = state.get("explore_context")
    canonical = plan.get("line") or (slots.get("line") or {}).get("canonical") or "this line"
    scope_label = explore_context_label(explore_context, canonical)
    summaries = line_context.get("dataset_summaries") or []
    system = load_prompt(
        "plan_benefits",
        canonical_line_name=canonical,
        scope_label=scope_label,
        plan_aims_json=json.dumps(plan.get("aims") or []),
        datasets_summary=json.dumps(summaries, indent=2),
    )
    llm = get_llm_client()
    response = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content="Benefits:")],
        caller="plan_benefits",
    )
    return (response.content or "").strip()


async def build_plan_message(state: ManagerState) -> ManagerState:
    debug_state("build_plan_message", state)
    state = {**state, "error": None}
    plan = dict(state.get("plan") or {})
    slots = state.get("slots") or {}
    time_slot = slots.get("time") or {}
    aims = plan.get("aims") or (slots.get("aim") or {}).get("aims") or []

    benefits = plan.get("benefits") or ""
    if not benefits and aims:
        try:
            benefits = await _generate_plan_benefits(state, plan)
            plan["benefits"] = benefits
        except Exception:
            benefits = ""

    msg = (
        "**Plan**\n"
        f"- **Line:** {plan.get('line') or (slots.get('line') or {}).get('canonical')}\n"
        f"- **Time:** {_plan_time_line(time_slot)}\n"
        f"- **Aims:**\n"
        + "\n".join(f"  - {a}" for a in aims)
    )
    if benefits:
        msg += f"\n\n**Benefits:**\n{benefits}"
    msg += "\n\nReply **go** to proceed, say *more options* for other plans, or tell me what to change."

    try:
        await broadcast_event(state.get("user_id", ""), {
            "topic": "manager.plan_built",
            "session_id": state.get("session_id", ""),
            "payload": {
                "line": plan.get("line"),
                "aims": plan.get("aims", []),
                "time_start": plan.get("time_start"),
                "time_end": plan.get("time_end"),
            },
        })
    except Exception:
        pass

    line_name = plan.get("line") or (slots.get("line") or {}).get("canonical") or "this line"
    explanation = f"Here's the analysis plan for **{line_name}**:"
    return {**state, "plan": plan, "agent_message": msg, "explanation": explanation, "phase": "plan"}


async def detect_confirm(state: ManagerState) -> ManagerState:
    debug_state("detect_confirm", state)
    state = {**state, "error": None}
    user_msg = (state.get("user_message") or "").strip().lower()
    confirmed = user_msg in _CONFIRM_WORDS
    if not confirmed:
        debug("detect_confirm", "not confirmed")
        return {**state, "task_confirmed": False, "phase": "extract"}

    from agents.manager.context.verification import sync_verification_context

    verification_context = await sync_verification_context(state)

    plan = state.get("plan") or {}
    slots = state.get("slots") or {}
    time_slot = slots.get("time") or {}
    time_range = None
    if not time_slot.get("no_filter") and time_slot.get("resolved"):
        time_range = {"start": time_slot.get("start"), "end": time_slot.get("end")}
    task_definition = {
        "aims": plan.get("aims") or (slots.get("aim") or {}).get("aims") or [],
        "alias_name": plan.get("alias_name") or plan.get("line"),
        "notes": plan.get("notes") or None,
        "time_range": time_range,
    }
    schema_payload = build_planner_schema_payload(
        state.get("line_context"), state.get("dataset_context")
    )
    task_definition["datasets_in_scope"] = schema_payload.get("datasets_in_scope") or []
    task_definition["datasets_excluded"] = schema_payload.get("datasets_excluded") or []
    debug("detect_confirm", "confirmed", verified=verification_context.get("verified"))
    return {
        **state,
        "task_confirmed": True,
        "task_definition": task_definition,
        "verification_context": verification_context,
        "phase": "confirm",
    }


async def save_task_definition_node(state: ManagerState) -> ManagerState:
    debug_state("save_task_definition", state)
    canonical = (state.get("slots") or {}).get("line", {}).get("canonical")
    if canonical and state.get("task_definition"):
        try:
            version = await save_task_definition(canonical, state["user_id"], state["task_definition"])
            debug("save_task_definition", "saved", line=canonical, version=version)
        except Exception:
            logger.exception("save_task_definition_node: DB save failed for %s", canonical)
    return {**state}


async def send_to_planner(state: ManagerState) -> ManagerState:
    debug_state("send_to_planner", state)
    line_context = state.get("line_context") or {}
    schema = line_context.get("schema") or {}
    slots = state.get("slots") or {}
    canonical = (slots.get("line") or {}).get("canonical") or ""

    schema_payload = build_planner_schema_payload(
        line_context, state.get("dataset_context")
    )

    payload = {
        "line_name": canonical,
        "schema": schema,
        "datasets": line_context.get("datasets") or schema.get("datasets") or [],
        "global_version": schema.get("global_version"),
        "task_definition": state.get("task_definition"),
        "time_range": (state.get("task_definition") or {}).get("time_range"),
        "datasets_in_scope": schema_payload.get("datasets_in_scope") or [],
        "datasets_excluded": schema_payload.get("datasets_excluded") or [],
        "dataset_schemas": schema_payload.get("dataset_schemas") or [],
        "join_catalog": schema_payload.get("join_catalog") or [],
        "saved_plans": state.get("saved_plans") or [],
        "iot_column_wishes": state.get("iot_column_wishes") or [],
        "session_goal": state.get("session_goal"),
    }
    logger.info("planner.start payload: %s", json.dumps(payload, default=str))

    # Set mode to man before publishing — guarantees ask→man before any worker races
    try:
        await update_session_mode(
            session_id=state.get("session_id", ""),
            user_id=state.get("user_id", ""),
            mode="man",
        )
    except Exception:
        logger.exception("send_to_planner: failed to set mode=man")

    # Publish to the event bus for planner agent consumption
    try:
        from bus.publisher import publish
        await publish(
            topic="planner.start",
            user_id=state.get("user_id", ""),
            session_id=state.get("session_id"),
            payload=payload,
        )
        logger.info("Published planner.start event for line=%s session=%s", canonical, state.get("session_id"))
    except Exception as exc:
        logger.warning("Failed to publish planner.start: %s", exc)

    aims = (state.get("task_definition") or {}).get("aims") or []
    debug("send_to_planner", "done", line=canonical, aims=aims)
    return {
        **state,
        "planner_payload": payload,
        "phase": "done",
        "agent_message": (
            f"Analysis plan saved and sent to the execution pipeline.\n\n"
            f"**Line:** {canonical}\n"
            f"**Aims:** {', '.join(aims)}\n\n"
            "Your analysis request has been queued. Results will appear here when ready."
        ),
    }
