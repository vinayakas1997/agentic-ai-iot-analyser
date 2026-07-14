import json
import logging
import re

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
            "source": line.get("source"),
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

    # Detect if user selected a suggested aim
    suggested_aims = (state.get("line_context") or {}).get("suggested_aims") or []
    selected_suggested = any(
        aim == user_message
        for s_aim in suggested_aims
        for aim in ([s_aim] if isinstance(s_aim, str) else [s_aim.get("aim")])
    )
    if selected_suggested:
        state["selected_suggested_aim"] = user_message

    # Reset explore_phase when line mention changes
    session_json = _build_session_json(state)
    if session_json.get("line", {}).get("mention") and not session_json.get("line", {}).get("resolved"):
        state["explore_phase"] = None

    state = {**state, "error": None, "analyst_reasoning": None, "tool_to_call": None, "tool_result": None}

    # Guard: handle edge-case tool results without LLM call
    last_output = session_json.get("last_tool_output")
    if isinstance(last_output, dict):
        # resolve_line: not_found
        if last_output.get("status") == "not_found":
            mention = last_output.get("mention") or "that line"
            hint = ""
            lower = mention.lower()
            for article in ("the ", "a ", "an "):
                if lower.startswith(article):
                    hint = f" Try removing the word '{article.strip()}' from the name."
                    break
            # Clear stale line mention so user can try a different name on next turn
            slots = dict(state.get("slots") or {})
            line = dict(slots.get("line") or {})
            line["mention"] = None
            line["canonical"] = None
            line["resolved"] = False
            slots["line"] = line
            slots["line_slots"] = []
            return {
                **state,
                "slots": slots,
                "agent_message": f"I couldn't find **{mention}** in the IoT catalog.{hint}\n\nPlease try another name or check the spelling.",
                "phase": "ask",
            }
        # resolve_line: ambiguous
        if last_output.get("status") == "ambiguous":
            mention = last_output.get("mention") or "that line"
            candidates = last_output.get("candidates") or []
            listed = ", ".join(f"**{c}**" for c in candidates)
            # Clear stale line mention so user can type the exact name
            slots = dict(state.get("slots") or {})
            line = dict(slots.get("line") or {})
            line["mention"] = None
            line["canonical"] = None
            line["resolved"] = False
            slots["line"] = line
            return {
                **state,
                "slots": slots,
                "agent_message": f'Multiple lines match **"{mention}"**: {listed}.\n\nPlease reply with the exact line name you want.',
                "phase": "ask",
            }
        # resolve_time: ambiguous
        if last_output.get("kind") == "ambiguous" and not session_json.get("time", {}).get("resolved"):
            raw = session_json.get("time", {}).get("raw") or "that phrase"
            interpretations = last_output.get("interpretations") or []
            if interpretations:
                listed = "\n".join(f"  - {item}" for item in interpretations)
                return {
                    **state,
                    "agent_message": f'Time phrase **"{raw}"** is unclear. Did you mean:\n{listed}\n\nPlease reply with one.',
                    "phase": "ask",
                }
        # resolve_time: invalid
        if last_output.get("kind") == "invalid" and not session_json.get("time", {}).get("resolved"):
            raw = session_json.get("time", {}).get("raw") or "that phrase"
            detail = last_output.get("reason", "could not parse time")
            return {
                **state,
                "agent_message": f'Could not understand time phrase **"{raw}"**: {detail}\n\nPlease rephrase the time range.',
                "phase": "ask",
            }

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
        # Guard: if user gave an aim and plan proposals are missing, generate plans
        has_aim = bool(session_json.get("aim", {}).get("raw") or session_json.get("aim", {}).get("aims"))
        if (
            not state.get("analysis_proposals")
            and session_json.get("line", {}).get("resolved")
            and session_json.get("schema_fetched")
            and has_aim
        ):
            result["tool_to_call"] = "generate_plans"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            return result

        result["agent_message"] = str(message or "Let me summarize what I've found and how we can proceed.").strip()
        result["phase"] = "ask"
        return result

    # If LLM says call_tool but tool name is missing/empty, treat as respond
    if action == "call_tool" and not tool:
        result["agent_message"] = str(message or "Let me summarize what I've found and how we can proceed.").strip()
        result["phase"] = "ask"
        return result

    if action == "call_tool" and tool:
        if tool_call_count >= 10:
            has_schema = session_json.get("schema_fetched")
            has_aim = bool(session_json.get("aim", {}).get("raw") or session_json.get("aim", {}).get("aims"))
            if has_schema and has_aim:
                result["tool_to_call"] = "generate_plans"
            elif has_schema:
                result["tool_to_call"] = "answer_advisory"
            else:
                result["agent_message"] = "I've gathered enough information. Let me summarize what I know and suggest next steps."
                result["phase"] = "ask"
                return result
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            return result

        # Guard: only allow confirm_plan via __confirm__ or confirm {n}
        if tool == "confirm_plan":
            user_msg = user_message.strip().lower()
            if user_msg == "__confirm__":
                pass
            elif re.match(r'^confirm\s+(\d+)$', user_msg):
                confirm_match = re.match(r'^confirm\s+(\d+)$', user_msg)
                proposal_idx = int(confirm_match.group(1)) - 1
                proposals = state.get("analysis_proposals") or []
                if 0 <= proposal_idx < len(proposals):
                    selected = proposals[proposal_idx]
                    result["plan"] = {
                        "aims": selected.get("aims", []),
                        "benefits": selected.get("what_you_might_see", ""),
                    }
                else:
                    result["agent_message"] = "Invalid proposal selection. Please try again."
                    result["phase"] = "ask"
                    return result
            else:
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
                    "Press **Go — proceed** to confirm and execute."
                )
                result["phase"] = "ask"
                return result

        # Guard: route "more options" to generate_plans instead of answer_advisory
        if tool == "answer_advisory" and any(
            phrase in user_message.lower() for phrase in ["more options", "another option", "another plan", "different options"]
        ):
            result["tool_to_call"] = "generate_plans"
            result["tool_call_count"] = tool_call_count + 1
            result["phase"] = "tool"
            return result

        # Guard: don't generate plans without a user-provided aim
        has_aim = bool(
            session_json.get("aim", {}).get("raw")
            or session_json.get("aim", {}).get("aims")
            or state.get("selected_suggested_aim")
        )
        if tool == "generate_plans" and not has_aim:
            result["tool_to_call"] = "answer_advisory"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
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

    # Treat unrecognized/missing action as respond
    result["agent_message"] = str(message or "Let me summarize what I've found and how we can proceed.").strip()
    result["phase"] = "ask"
    return result
