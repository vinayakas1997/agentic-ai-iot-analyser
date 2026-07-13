"""Serialize/deserialize manager session state for PostgreSQL storage."""

import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

PERSISTED_STATE_KEYS = (
    "reference_now",
    "reference_timezone",
    "slots",
    "line_context",
    "plan",
    "phase",
    "chat_history",
    "task_confirmed",
    "task_definition",
    "planner_payload",
    "analysis_proposals",
    "explore_phase",
    "aim_exploration",
    "explore_context",
    "dataset_context",
    "session_inventory",
    "session_intent",
    "verification_context",
    "reuse_alias",
    "saved_plans",
    "session_goal",
    "user_explore_intent",
    "scope_selection",
    "scope_pending",
    "iot_column_wishes",
)


def _message_to_dict(msg: BaseMessage) -> dict:
    if isinstance(msg, HumanMessage):
        role = "user"
    elif isinstance(msg, AIMessage):
        role = "assistant"
    else:
        role = getattr(msg, "type", "unknown")
    content = msg.content
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
        content = "\n".join(texts) if texts else json.dumps(content)
    elif not isinstance(content, str):
        content = str(content) if content is not None else ""
    return {"role": role, "content": content}


def _dict_to_message(item: dict) -> BaseMessage:
    role = item.get("role", "")
    content = item.get("content", "")
    if not isinstance(content, str):
        content = str(content) if content is not None else ""
    if role == "user":
        return HumanMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    return AIMessage(content=content)


def _serialize_chat_history(chat_history: list | None) -> list[dict]:
    if not chat_history:
        return []
    out: list[dict] = []
    for item in chat_history:
        if isinstance(item, (HumanMessage, AIMessage)):
            out.append(_message_to_dict(item))
        elif isinstance(item, dict) and "role" in item and "content" in item:
            out.append({"role": item["role"], "content": item["content"]})
    return out


def _deserialize_chat_history(data: list | None) -> list[BaseMessage]:
    if not data:
        return []
    return [_dict_to_message(item) for item in data if isinstance(item, dict)]


def _build_planner_schema_payload(line_context: dict | None, dataset_context: dict | None) -> dict:
    if not line_context:
        return {
            "datasets_in_scope": [],
            "datasets_excluded": [],
            "dataset_schemas": [],
            "join_catalog": [],
        }
    line_name = line_context.get("line_name")
    entry = (dataset_context or {}).get("by_line", {}).get(line_name) or {}
    return {
        "datasets_in_scope": line_context.get("datasets_in_scope") or entry.get("included") or [],
        "datasets_excluded": line_context.get("datasets_excluded") or entry.get("excluded") or [],
        "dataset_schemas": line_context.get("datasets_full") or [],
        "join_catalog": line_context.get("join_catalog") or [],
    }


def canonical_line_from_state(state: dict) -> str | None:
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    canonical = line.get("canonical")
    return canonical if canonical else None


def session_status_from_state(state: dict) -> str:
    if state.get("phase") == "done":
        return "completed"
    return "active"


def state_to_json(state: dict) -> dict:
    """Extract JSON-safe persisted subset from a manager turn result."""
    out: dict = {}
    for key in PERSISTED_STATE_KEYS:
        if key not in state:
            continue
        value = state[key]
        if key == "chat_history":
            out[key] = _serialize_chat_history(value)
        else:
            out[key] = value
    return out


def state_from_json(data: dict | None) -> dict | None:
    """Restore persisted state dict for run_manager_agent existing_state."""
    if not data:
        return None
    out = dict(data)
    if "chat_history" in out:
        out["chat_history"] = _deserialize_chat_history(out.get("chat_history"))
    return out


def build_schema_summary(state: dict) -> dict:
    """Compact schema snapshot for the context panel at a given turn."""
    line_context = state.get("line_context") or {}
    dataset_context = state.get("dataset_context") or {}
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    time_slot = slots.get("time") or {}

    schema_payload = _build_planner_schema_payload(line_context, dataset_context)
    datasets_full = schema_payload.get("dataset_schemas") or line_context.get("datasets_full") or []

    columns: list[dict] = []
    datasets: list[dict] = []
    for ds in datasets_full:
        if not isinstance(ds, dict):
            continue
        dataset_name = ds.get("dataset_name") or ds.get("name") or "?"
        datasets.append(
            {
                "name": dataset_name,
                "table": ds.get("table"),
                "role": ds.get("role"),
                "description": ds.get("description"),
                "data_earliest_ts": ds.get("data_earliest_ts"),
            }
        )
        for col in ds.get("column_definitions") or []:
            if not isinstance(col, dict):
                continue
            columns.append(
                {
                    "dataset": dataset_name,
                    "name": col.get("name"),
                    "datatype": col.get("datatype"),
                    "meaning": col.get("meaning"),
                }
            )

    time_range = None
    if not time_slot.get("no_filter") and time_slot.get("resolved"):
        time_range = {"start": time_slot.get("start"), "end": time_slot.get("end")}

    time_pending = None
    if time_slot.get("mentioned") and not time_slot.get("resolved") and not time_slot.get("no_filter"):
        time_pending = time_slot.get("raw") or "pending"

    line_match = None
    if line.get("resolved") and line.get("canonical"):
        line_match = {
            "mention": line.get("mention"),
            "canonical": line.get("canonical"),
            "source": line.get("source"),
        }

    return {
        "line": line.get("canonical") or line.get("mention") or line_context.get("line_name"),
        "line_match": line_match,
        "datasets": datasets,
        "suggested_aims": list(line_context.get("suggested_aims") or []),
        "datasets_in_scope": schema_payload.get("datasets_in_scope") or [],
        "datasets_excluded": schema_payload.get("datasets_excluded") or [],
        "columns": columns,
        "joins": schema_payload.get("join_catalog") or [],
        "time": time_range,
        "time_pending": time_pending,
        "no_time_filter": bool(time_slot.get("no_filter")),
    }


def build_turn_snapshot(state: dict) -> dict:
    return {
        "ui": build_ui_summary(state),
        "schema": build_schema_summary(state),
    }


def pair_messages_to_turns(rows: list[dict]) -> list[dict]:
    """Pair user+agent chat_history rows into turn timeline."""
    by_index: dict[int, dict] = {}
    for row in rows:
        idx = row.get("turn_index")
        if idx is None:
            continue
        turn = by_index.setdefault(
            idx,
            {
                "turn_index": idx,
                "user": "",
                "agent": "",
                "ui": None,
                "schema": None,
                "created_at": row.get("created_at"),
            },
        )
        role = row.get("role")
        if role == "user":
            turn["user"] = row.get("content") or ""
            if row.get("created_at"):
                turn["created_at"] = row["created_at"]
        elif role == "agent":
            turn["agent"] = row.get("content") or ""
            turn["ui"] = row.get("ui_snapshot")
            turn["schema"] = row.get("schema_snapshot")
            if row.get("created_at"):
                turn["created_at"] = row["created_at"]

    return [by_index[k] for k in sorted(by_index.keys())]


def build_provenance(suggested_aims: list[str] | None, proposals: list[dict] | None) -> list[dict]:
    """Map suggested aims to proposal fulfillments by fuzzy matching."""
    if not suggested_aims or not proposals:
        return []
    lower_suggested = [a.lower() for a in suggested_aims]
    result = []
    for aim in suggested_aims:
        ids: list[int] = []
        for p in proposals:
            p_aims = p.get("aims") or []
            for pa in p_aims:
                lower = pa.lower()
                matched = any(lower in sa or sa in lower for sa in lower_suggested)
                if matched:
                    ids.append(p.get("id", 0))
                    break
        result.append({"suggestedAim": aim, "fulfilledByProposalIds": ids})
    return result


def build_ui_summary(state: dict) -> dict:
    """Thin projection for API clients / future frontend."""
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    line_context = state.get("line_context") or {}
    next_step = state.get("message_next_step")
    phase = state.get("phase", "extract")
    done = phase == "done"

    actions = []
    if phase != "man":
        proposals = state.get("analysis_proposals")
        plan = state.get("plan")
        if proposals:
            actions.append({"label": "See more options", "msg": "more options"})
        elif plan and plan.get("aims") and not done:
            actions.append({"label": "Go — proceed", "msg": "__confirm__", "primary": True})
            actions.append({"label": "More options", "msg": "more options"})
    show_change = bool(state.get("analysis_proposals") or (state.get("plan") and state["plan"].get("aims") and not done))

    return {
        "phase": phase,
        "line": line.get("canonical") or line.get("mention"),
        "missing": state.get("missing") or [],
        "plan": state.get("plan"),
        "proposals": state.get("analysis_proposals"),
        "saved_plans": state.get("saved_plans") or [],
        "scope_pending": bool(state.get("scope_pending")),
        "done": done,
        "planner_payload": state.get("planner_payload"),
        "next_step": next_step,
        "suggested_aims": list(line_context.get("suggested_aims") or []),
        "explanation": state.get("explanation"),
        "actions": actions,
        "show_change": show_change,
        "proposal_provenance": build_provenance(
            list(line_context.get("suggested_aims") or []),
            state.get("analysis_proposals"),
        ),
    }


def format_turn_response(
    state: dict,
    session_id: str,
    *,
    turn_index: int | None = None,
) -> dict:
    """Standard API response after one manager turn."""
    status = session_status_from_state(state)
    snapshot = build_turn_snapshot(state)
    next_step = snapshot["ui"].get("next_step")
    return {
        "session_id": session_id,
        "turn_index": turn_index,
        "agent_message": state.get("agent_message") or "",
        "next_step": next_step,
        "phase": state.get("phase", "extract"),
        "status": status,
        "ui": snapshot["ui"],
        "schema": snapshot["schema"],
        "done": status == "completed",
        "planner_payload": state.get("planner_payload"),
    }
