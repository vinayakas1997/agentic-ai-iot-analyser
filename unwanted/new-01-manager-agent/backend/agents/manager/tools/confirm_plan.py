import json
import logging

from api.websocket import broadcast_event
from agents.manager.db import save_task_definition
from agents.manager.state import ManagerState
from agents.manager.utils.schema_utils import build_planner_schema_payload

logger = logging.getLogger(__name__)


async def tool_confirm_plan(state: ManagerState) -> ManagerState:
    logger.debug("tool_confirm_plan: starting")

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

    line_context = state.get("line_context") or {}
    dataset_context = state.get("dataset_context") or {}

    datasets_in_scope = list(line_context.get("dataset_summaries") or [])
    task_definition["datasets_in_scope"] = [d.get("dataset_name") for d in datasets_in_scope if d.get("dataset_name")]
    task_definition["datasets_excluded"] = []

    canonical = plan.get("line") or (slots.get("line") or {}).get("canonical")
    if canonical and task_definition:
        try:
            await save_task_definition(canonical, state["user_id"], task_definition)
        except Exception:
            logger.exception("confirm_plan: save_task_definition failed")

    schema_payload = build_planner_schema_payload(line_context, dataset_context)

    payload = {
        "line_name": canonical,
        "task_definition": task_definition,
        "time_range": time_range,
        "datasets_in_scope": task_definition["datasets_in_scope"],
        "datasets_excluded": [],
        "schema": schema_payload,
        "datasets": task_definition["datasets_in_scope"],
        "global_version": datasets_in_scope[0].get("global_version") if datasets_in_scope else 1,
        "dataset_schemas": schema_payload.get("dataset_schemas") or [],
        "join_catalog": schema_payload.get("join_catalog") or [],
        "iot_column_wishes": state.get("iot_column_wishes") or [],
        "saved_plans": state.get("saved_plans") or [],
        "session_goal": state.get("session_goal"),
    }

    try:
        from bus.publisher import publish
        await publish(
            topic="planner.start",
            user_id=state.get("user_id", ""),
            session_id=state.get("session_id"),
            payload=payload,
        )
    except Exception as e:
        logger.warning("confirm_plan: publish failed: %s", e)

    try:
        await broadcast_event(state.get("user_id", ""), {
            "topic": "manager.plan_built",
            "session_id": state.get("session_id", ""),
            "payload": {
                "line": canonical,
                "aims": task_definition.get("aims", []),
                "time_start": time_range.get("start") if time_range else None,
                "time_end": time_range.get("end") if time_range else None,
            },
        })
    except Exception:
        logger.warning("confirm_plan: broadcast_event failed", exc_info=True)

    aims_list = task_definition.get("aims", [])
    msg = (
        f"Analysis plan saved and sent to the execution pipeline.\n\n"
        f"**Line:** {canonical}\n"
        f"**Aims:** {', '.join(aims_list)}\n\n"
        "Your analysis request has been queued."
    )

    return {
        **state,
        "analysis_proposals": None,
        "task_confirmed": True,
        "task_definition": task_definition,
        "planner_payload": payload,
        "phase": "man",
        "agent_message": msg,
        "tool_result": json.dumps({"status": "confirmed", "payload": payload}),
    }



