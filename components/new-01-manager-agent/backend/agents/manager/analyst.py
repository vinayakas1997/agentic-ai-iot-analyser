import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


def _build_session_json(state: ManagerState) -> dict:
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    time = slots.get("time") or {}
    aim = slots.get("aim") or {}
    scope = slots.get("scope") or {}

    tool_result = state.get("tool_result")
    last_tool_output = None
    if tool_result:
        try:
            last_tool_output = json.loads(tool_result)
        except (json.JSONDecodeError, TypeError):
            last_tool_output = tool_result

    line_context = state.get("line_context")
    schema_fetched = bool(line_context and line_context.get("datasets"))

    result = {
        "phase": state.get("phase", "extract"),
        "last_tool_output": last_tool_output,
        "tool_call_count": state.get("tool_call_count", 0),
        "schema_fetched": schema_fetched,
        "line": {
            "mention": line.get("mention"),
            "canonical": line.get("canonical"),
            "resolved": line.get("resolved", False),
        },
        "time": {
            "raw": time.get("raw"),
            "mentioned": time.get("mentioned", False),
            "resolved": time.get("resolved", False),
            "start": time.get("start"),
            "end": time.get("end"),
            "ambiguous": time.get("ambiguous", False),
            "interpretations": time.get("interpretations", []),
            "no_filter": time.get("no_filter", False),
        },
        "aim": {
            "raw": aim.get("raw"),
            "aims": aim.get("aims", []),
            "reorganized": aim.get("reorganized", False),
        },
        "scope": {
            "intent_mode": scope.get("intent_mode", "single"),
            "slot_count": scope.get("slot_count", 0),
        },
        "line_slots": [
            {
                "mention": s.get("mention"),
                "canonical": s.get("canonical"),
                "status": s.get("status"),
                "skipped": s.get("skipped", False),
            }
            for s in (slots.get("line_slots") or [])
        ],
        "active_line_index": slots.get("active_line_index"),
        "has_plan": bool(state.get("plan")),
        "plan": state.get("plan"),
        "session_goal": state.get("session_goal"),
        "saved_plans": [
            {"id": p.get("id"), "title": p.get("title")}
            for p in (state.get("saved_plans") or [])
            if isinstance(p, dict)
        ],
    }
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


async def analyst(state: ManagerState) -> ManagerState:
    logger.debug("analyst: starting")
    user_message = (state.get("user_message") or "").strip()

    session_json = _build_session_json(state)

    state = {**state, "error": None, "analyst_reasoning": None, "tool_to_call": None, "tool_result": None}

    if not user_message:
        return {**state, "phase": "extract"}

    chat_history = _format_chat_history(state.get("chat_history"))

    history_block = ""
    if chat_history:
        history_block = f"\n\nRecent conversation:\n{chat_history}"

    system = load_prompt(
        "analyst",
        session_state_json=json.dumps(session_json, indent=2),
        user_message=user_message,
    )
    system += history_block

    messages = [SystemMessage(content=system), HumanMessage(content=user_message)]

    llm = get_llm_client()
    try:
        response = await llm.ainvoke(messages, caller="analyst")
    except Exception as e:
        logger.exception("analyst: LLM call failed")
        return {**state, "error": "llm_failed", "phase": "extract"}

    try:
        parsed = parse_json_from_message(response.content or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}

    reasoning = parsed.get("reasoning") or ""
    action = (parsed.get("action") or "respond").strip().lower()
    message = parsed.get("message")
    tool = parsed.get("tool")
    tool_input = parsed.get("tool_input") or {}

    raw_content = response.content
    if isinstance(raw_content, list):
        raw_text = " ".join(c.get("text", str(c)) if isinstance(c, dict) else str(c) for c in raw_content)
    else:
        raw_text = str(raw_content or "")
    logger.info("analyst: raw_response=%s", raw_text[:500])
    logger.info("analyst: action=%s reasoning=%s tool=%s tool_input=%s", action, reasoning, tool, tool_input)

    tool_call_count = state.get("tool_call_count", 0)

    result = {
        **state,
        "analyst_reasoning": reasoning,
        "tool_to_call": tool if action == "call_tool" else None,
        "tool_result": None,
    }

    if action == "respond":
        # Guard: if all slots ready but no proposals yet, generate plans instead of responding
        if (
            not state.get("analysis_proposals")
            and session_json.get("line", {}).get("resolved")
            and session_json.get("schema_fetched")
        ):
            result["tool_to_call"] = "generate_plans"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            return result

        result["agent_message"] = str(message or "Let me summarize what I've found and how we can proceed.").strip()
        result["phase"] = "ask"
        return result

    if action == "call_tool" and tool:
        if tool_call_count >= 10:
            result["agent_message"] = "I've gathered enough information. Let me summarize what I know and suggest next steps."
            result["phase"] = "ask"
            return result

        # Guard: prevent auto-confirm without user saying go/confirm/yes/proceed/ok
        _CONFIRM_WORDS = ("go", "confirm", "yes", "proceed", "ok")
        if tool == "confirm_plan" and user_message.lower().strip() not in _CONFIRM_WORDS:
            plan = session_json.get("plan") or {}
            aim_items = plan.get("aims") or []
            if not aim_items:
                proposals = state.get("analysis_proposals") or []
                for p in proposals:
                    if isinstance(p, dict):
                        aim_items.extend(p.get("aims") or [])
            aims_text = "\n".join(f"- {a[:120]}" for a in aim_items[:5])
            canonical = session_json.get("line", {}).get("canonical") or ""
            result["agent_message"] = (
                f"The analysis plan is ready for **{canonical}**.\n\n"
                f"**Aims:**\n{aims_text}\n\n"
                "Would you like to proceed? Press **Go — proceed** to confirm and execute."
            )
            result["phase"] = "plan"
            return result

        # Guard: skip fetch_schema if already fetched
        if tool == "fetch_schema" and session_json.get("schema_fetched"):
            result["tool_to_call"] = "reorganize_aims" if not session_json.get("aim", {}).get("reorganized") else "generate_plans"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            return result

        # Guard: skip extract_slots if line already mentioned
        if tool == "extract_slots" and session_json.get("line", {}).get("mention"):
            result["tool_to_call"] = "resolve_line" if not session_json.get("line", {}).get("resolved") else "fetch_schema"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            return result

        result["tool_call_count"] = tool_call_count + 1
        result["phase"] = "tool"
        return result

    result["phase"] = "extract"
    return result
