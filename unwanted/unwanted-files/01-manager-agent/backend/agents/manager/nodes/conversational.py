import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.chat_memory import get_recent_chat_messages
from agents.manager.debug_log import debug, debug_state
from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.slots import session_state_for_llm
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


def _build_data_availability(state: ManagerState) -> str:
    line_context = state.get("line_context")
    if not line_context:
        return ""
    summaries = line_context.get("dataset_summaries") or []
    parts = []
    for ds in summaries:
        name = ds.get("dataset_name") or "?"
        earliest = ds.get("data_earliest_ts")
        if earliest:
            parts.append(f"- {name}: data available from {earliest}")
        else:
            parts.append(f"- {name}: no date range info")
    if not parts:
        return ""
    return "Available datasets:\n" + "\n".join(parts)


async def analyze_conversational(state: ManagerState) -> ManagerState:
    debug_state("analyze_conversational", state)
    state = {**state, "error": None}
    user_message = (state.get("user_message") or "").strip()

    if not user_message:
        return {**state, "phase": "extract", "conversational_intent": "extract"}

    slots = state.get("slots") or {}
    session_json = session_state_for_llm(
        slots,
        phase=state.get("phase", ""),
        explore_phase=state.get("explore_phase"),
        analysis_proposals=state.get("analysis_proposals"),
        has_plan=bool(state.get("plan")),
        state=state,
    )

    data_availability = _build_data_availability(state)

    system = load_prompt(
        "conversational_analysis",
        session_state_json=json.dumps(session_json, indent=2),
        data_availability_summary=data_availability,
        chat_history=_format_chat_history(state.get("chat_history")),
        session_goal=state.get("session_goal") or "not yet known",
        user_message=user_message,
    )

    debug("analyze_conversational", "calling LLM", user_message=user_message)

    messages = [SystemMessage(content=system)]
    if not data_availability:
        chat_msgs = get_recent_chat_messages(state.get("chat_history"))
        messages.extend(chat_msgs)
    messages.append(HumanMessage(content=user_message))

    llm = get_llm_client()
    try:
        response = await llm.ainvoke(messages, caller="analyze_conversational")
    except Exception:
        logger.exception("analyze_conversational: LLM call failed")
        return {**state, "error": "llm_failed", "phase": "extract", "conversational_intent": "extract"}

    try:
        parsed = parse_json_from_message(response.content or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}

    intent = (parsed.get("intent") or "extract").strip().lower()
    reasoning = parsed.get("reasoning") or ""
    conversational_response = parsed.get("conversational_response")
    hints = parsed.get("extraction_hints") or {}

    debug("analyze_conversational", "parsed", intent=intent, reasoning=reasoning)

    result = {
        **state,
        "conversational_intent": intent,
        "conversational_reasoning": reasoning,
    }

    if intent == "converse" and conversational_response:
        result["agent_message"] = str(conversational_response).strip()
        result["phase"] = "ask"
        return result

    result["phase"] = "extract"
    return result


def _format_chat_history(chat_history: list | None) -> str:
    if not chat_history:
        return ""
    lines = []
    for msg in chat_history:
        if hasattr(msg, "type") and hasattr(msg, "content"):
            role = "user" if msg.type == "human" else "assistant"
            lines.append(f"{role}: {msg.content}")
        elif isinstance(msg, dict):
            lines.append(f"{msg.get('role', '?')}: {msg.get('content', '')}")
    return "\n".join(lines[-6:])
