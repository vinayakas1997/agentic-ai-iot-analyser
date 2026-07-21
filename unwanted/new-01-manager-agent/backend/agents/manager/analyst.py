import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


def _format_benefits_from_text(raw: str) -> list[str]:
    """Split a free-text benefits string into separate bullet points."""
    if not raw:
        return []
    parts = re.split(r'(?<=[.!])\s+(?=[A-Z])', raw.strip())
    return [p.strip() for p in parts if p.strip()]


def _relevant_columns(datasets_full: list, aims_text: str) -> list[dict]:
    """Find column names mentioned in the aims text, grouped by dataset.

    Only columns whose name appears in the aim description are returned,
    so the user sees the subset that the analysis actually touches.
    """
    aim_lower = aims_text.lower()
    result = []
    for ds in datasets_full:
        name = ds.get("dataset_name") or ds.get("name") or ""
        if not name:
            continue
        matched: list[str] = []
        for col in (ds.get("column_definitions") or []):
            col_name = col.get("name", "")
            if col_name and col_name.lower() in aim_lower and col_name not in matched:
                matched.append(col_name)
        if matched:
            result.append({"dataset": name, "columns": matched})
    return result


def _format_columns_natural(columns_data: list[dict]) -> str:
    """Render the 'Data & columns used' section as natural-language lines."""
    if not columns_data:
        return ""
    lines: list[str] = []
    for entry in columns_data:
        cols = entry["columns"]
        if not cols:
            continue
        quoted = [f"'{c}'" for c in cols]
        if len(quoted) == 1:
            col_text = quoted[0]
        elif len(quoted) == 2:
            col_text = f"{quoted[0]} and {quoted[1]}"
        else:
            col_text = ", ".join(quoted[:-1]) + f", and {quoted[-1]}"
        lines.append(f"- *{entry['dataset']}* has {col_text}")
    return "\n".join(lines)


def _format_join_explanation(line_context: dict | None) -> str:
    """Return a join-explanation line from the join_catalog."""
    join_catalog = (line_context or {}).get("join_catalog") or []
    lines: list[str] = []
    for j in join_catalog:
        from_ds = j.get("from_dataset") or ""
        to_ds = j.get("to_dataset") or ""
        on_keys = j.get("on") or []
        note = j.get("note") or ""
        if from_ds and to_ds and on_keys:
            key_list = ", ".join(f"'{k}'" for k in on_keys)
            parts = [f"Join on {key_list} between **{from_ds}** and **{to_ds}**"]
            if note:
                parts.append(f"_{note}_")
            lines.append("- " + " — ".join(parts))
    return "\n".join(lines)


def _handle_confirm(state: ManagerState, user_msg: str, session_json: dict) -> ManagerState:
    """Handle confirm_plan routing deterministically, bypassing the LLM entirely.

    Covers all three cases:
    - ``__confirm__`` → mark the plan for execution (tool_to_call="confirm_plan")
    - ``confirm N``  → select proposal N for review (narrow plan, show review card)
    - anything else confirm-like → show the current plan summary with instructions.
    """
    tool_call_count = state.get("tool_call_count", 0)
    if user_msg == "__confirm__":
        return {
            **state,
            "analyst_reasoning": None,
            "tool_to_call": "confirm_plan",
            "tool_result": None,
            "tool_call_count": tool_call_count + 1,
            "phase": "tool",
        }

    confirm_match = re.match(r'^confirm\s+(sug|cus|pro)-(\d+)$', user_msg)
    if confirm_match:
        prefix = confirm_match.group(1)
        confirm_id = f"{prefix}-{confirm_match.group(2)}"
        if prefix == "pro":
            proposals = state.get("analysis_proposals") or []
            for idx, p in enumerate(proposals):
                if p.get("confirm_id") == confirm_id:
                    selected = proposals[idx]
                    canonical = session_json.get("line", {}).get("canonical") or ""
                    title = selected.get("title") or ""
                    feasible = selected.get("feasible", True)
                    benefits_raw = selected.get("what_you_might_see") or ""
                    aims = selected.get("aims") or []
                    feasibility_tag = "(Doable)" if feasible else "(Not doable)"

                    aims_text = "\n".join(f"- {a}" for a in aims[:5])

                    line_context = state.get("line_context")
                    datasets_full = (line_context or {}).get("datasets_full") or []
                    columns_data = _relevant_columns(datasets_full, aims_text)
                    columns_natural = _format_columns_natural(columns_data)
                    join_text = _format_join_explanation(line_context)

                    benefit_parts = _format_benefits_from_text(benefits_raw)
                    if len(benefit_parts) < 2 and aims:
                        benefit_parts.append("Leverages join keys and relevant columns across datasets for comprehensive analysis.")
                    benefits_text = "\n".join(f"- {b}" for b in benefit_parts) if benefit_parts else ""

                    msg = f"Here's the analysis plan for **{canonical}**"
                    msg += f": {title} {feasibility_tag}" if title else ""
                    msg += f"\n\n**What it does:**\n{aims_text}\n"
                    if columns_natural:
                        msg += f"\n**Data & columns used:**\n{columns_natural}\n"
                    if join_text:
                        msg += f"{join_text}\n"
                    if benefits_text:
                        msg += f"\n**Benefits:**\n{benefits_text}\n"
                    msg += (
                        "\n---\n"
                        "**How to proceed:**\n"
                        "- ✅ **Go — proceed** if you're satisfied with this plan\n"
                        "- 🔄 **More options** for fresh alternatives\n"
                        "- ✏️ **Change something** to modify details of this plan"
                    )
                    return {
                        **state,
                        "analyst_reasoning": None,
                        "tool_to_call": None,
                        "tool_result": None,
                        "plan": {
                            "aims": aims,
                            "benefits": benefits_text.strip(),
                            "line": canonical,
                        },
                        "analysis_proposals": proposals,
                        "selected_proposal_index": confirm_id,
                        "agent_message": msg,
                        "phase": "ask",
                    }
            return {
                **state,
                "analyst_reasoning": None,
                "tool_to_call": None,
                "tool_result": None,
                "agent_message": "Invalid proposal selection. Please try again.",
                "phase": "ask",
            }
        # sug- or cus- prefix — find aim
        if prefix == "sug":
            aims_list = (state.get("line_context") or {}).get("suggested_aims") or []
        else:
            aims_list = state.get("custom_aims") or []
        for item in aims_list:
            if item.get("confirm_id") == confirm_id:
                aim_text = item.get("aim", "")
                return {
                    **state,
                    "analyst_reasoning": None,
                    "selected_suggested_aim": aim_text,
                    "user_message": aim_text,
                    "tool_to_call": "generate_plans",
                    "tool_result": None,
                    "tool_call_count": tool_call_count + 1,
                    "phase": "tool",
                }
        return {
            **state,
            "analyst_reasoning": None,
            "tool_to_call": None,
            "tool_result": None,
            "agent_message": "Invalid aim selection. Please try again.",
            "phase": "ask",
        }

    # Fallback: confirm-like message that didn't match known patterns —
    # show the current plan summary with instructions.
    plan = session_json.get("plan") or {}
    aim_items = plan.get("aims") or []
    if not aim_items:
        for p in (state.get("analysis_proposals") or []):
            if isinstance(p, dict):
                aim_items.extend(p.get("aims") or [])
    aims_text = "\n".join(f"- {a[:120]}" for a in aim_items[:5])
    canonical = session_json.get("line", {}).get("canonical") or ""
    return {
        **state,
        "analyst_reasoning": None,
        "tool_to_call": None,
        "tool_result": None,
        "agent_message": (
            f"The analysis plan is ready for **{canonical}**.\n\n"
            f"**Aims:**\n{aims_text}\n\n"
            "Press **Go — proceed** to confirm and execute."
        ),
        "phase": "ask",
    }


def _detect_tool_loop(state: ManagerState, session_json: dict) -> str | None:
    """Detect if the agent is stuck calling the same tool with no progress.

    Returns an honest, actionable message if a loop is detected, or None to
    proceed normally.  The threshold is 3+ identical consecutive tool calls
    without meaningful state advancement (line unresolved, schema unfetched).
    """
    history = state.get("tool_call_history") or []
    if len(history) < 3:
        return None
    last_three = history[-3:]
    if len(set(last_three)) > 1:
        return None

    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    line_mention = line.get("mention")
    line_resolved = line.get("resolved")

    # If line resolved and schema fetched, progress is being made — not a loop.
    if line_resolved and session_json.get("schema_fetched"):
        return None

    tool = last_three[0]
    if tool in ("extract_slots", "resolve_line"):
        if line_mention:
            return (
                f"I'm having trouble resolving **{line_mention}** to a known production line. "
                "Could you double-check the spelling, or give me the exact line name?"
            )
        return (
            "I couldn't figure out which production line or machine you're asking about. "
            "Could you tell me the exact line name (e.g. FRUITS_TEST)?"
        )

    return (
        "I seem to be having trouble processing your request. "
        "Could you rephrase or provide more details?"
    )


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
        "analysis_proposals": state.get("analysis_proposals"),
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


def _ensure_suggested_aims_numbered(state: dict) -> dict:
    lc = state.get("line_context") or {}
    sa = lc.get("suggested_aims") or []
    if not sa:
        return state
    if all(s.get("display_number") for s in sa):
        return state
    for i, s in enumerate(sa):
        if not s.get("display_number"):
            s["display_number"] = i + 1
        if not s.get("confirm_id"):
            s["confirm_id"] = f"sug-{i + 1}"
    lc["suggested_aims"] = sa
    return state


async def analyst(state: ManagerState) -> ManagerState:
    logger.debug("analyst: starting")
    user_message = (state.get("user_message") or "").strip()

    state = _ensure_suggested_aims_numbered(state)

    # Pre-check: route confirm actions deterministically, bypassing the LLM
    # entirely. The LLM's probabilistic tool-choice is the root cause of
    # §3.8-type failures; this pre-check eliminates that failure mode
    # categorically for all confirmation-related messages.
    user_msg = user_message.strip().lower()
    if user_msg == "__confirm__" or re.match(r'^confirm\s+\d+$', user_msg) or re.match(r'^confirm\s+(sug|cus|pro)-\d+$', user_msg):
        session_json = _build_session_json(state)
        return _handle_confirm(state, user_msg, session_json)

    # Detect if user selected a suggested aim. Match fuzzily (not just exact
    # equality) since users usually paraphrase ("average cost by fruit")
    # rather than typing the full registry sentence ("Calculate average cost
    # by fruit for the FRUITS_TEST line using the fruits dataset.") — an
    # exact-only check never fires for typed follow-ups, which left
    # tool_generate_plans unable to narrow proposals and caused it to dump
    # every proposal's aims into the plan.
    suggested_aims = (state.get("line_context") or {}).get("suggested_aims") or []
    user_message_norm = user_message.strip().lower()
    matched_suggested_aim = None
    if user_message_norm:
        for s_aim in suggested_aims:
            aim_text = s_aim if isinstance(s_aim, str) else s_aim.get("aim")
            if not aim_text:
                continue
            aim_norm = aim_text.strip().lower()
            if aim_norm == user_message_norm or user_message_norm in aim_norm or aim_norm in user_message_norm:
                matched_suggested_aim = aim_text
                break
    if matched_suggested_aim:
        state["selected_suggested_aim"] = matched_suggested_aim
        if not state.get("analysis_proposals"):
            return {
                **state,
                "selected_suggested_aim": matched_suggested_aim,
                "tool_to_call": "generate_plans",
                "tool_call_count": state.get("tool_call_count", 0) + 1,
                "tool_call_history": list(state.get("tool_call_history") or []) + ["generate_plans"],
                "phase": "tool",
                "analyst_reasoning": None,
                "tool_result": None,
            }

    # Guard: route "more options" directly to generate_plans without LLM
    if state.get("analysis_proposals") and any(
        phrase in user_message.strip().lower() for phrase in ["more options", "another option", "another plan", "different options"]
    ):
        return {
            **state,
            "tool_to_call": "generate_plans",
            "tool_call_count": state.get("tool_call_count", 0) + 1,
            "tool_call_history": list(state.get("tool_call_history") or []) + ["generate_plans"],
            "phase": "tool",
            "analyst_reasoning": None,
            "tool_result": None,
        }

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

    system = load_prompt(
        "analyst",
        session_state_json=json.dumps(session_json, indent=2),
    )

    messages = [SystemMessage(content=system)]

    chat_history = state.get("chat_history") or []
    for msg in chat_history[-6:]:
        if hasattr(msg, "type") and hasattr(msg, "content"):
            if msg.type == "human":
                messages.append(HumanMessage(content=msg.content))
            elif msg.type == "ai":
                messages.append(AIMessage(content=msg.content))
        elif isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))

    messages.append(HumanMessage(content=user_message))

    # Circuit breaker: detect repeated identical tool calls without progress.
    # This catches extraction/resolution loops early (within 3 repeats) rather
    # than waiting for tool_call_count >= 10 (60-90+ seconds of wall time).
    # Also clears the stuck line mention so the next message gets a clean retry.
    cb_reason = _detect_tool_loop(state, session_json)
    if cb_reason:
        slots = dict(state.get("slots") or {})
        line = dict(slots.get("line") or {})
        line["mention"] = None
        slots["line"] = line
        return {
            **state,
            "slots": slots,
            "agent_message": cb_reason,
            "phase": "ask",
            "tool_to_call": None,
            "tool_result": None,
        }

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

    # Track tool decisions for loop detection.
    # Only the LLM's raw choice is appended here.  Guard overrides below
    # will replace the last entry with the actual tool so the loop
    # detector sees real execution, not LLM intention.
    tool_call_history = list(state.get("tool_call_history") or [])
    if action == "call_tool" and tool:
        tool_call_history.append(tool)

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
        "tool_call_history": tool_call_history,
    }

    if action == "respond":
        # Guard: if user gave an aim and plan proposals are missing, generate plans
        has_aim = bool(session_json.get("aim", {}).get("raw") or session_json.get("aim", {}).get("aims") or state.get("selected_suggested_aim"))
        if (
            not state.get("analysis_proposals")
            and session_json.get("line", {}).get("resolved")
            and session_json.get("schema_fetched")
            and has_aim
        ):
            result["tool_to_call"] = "generate_plans"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            result["tool_call_history"] = list(tool_call_history[:-1]) + ["generate_plans"]
            # Custom aim numbering for respond→generate_plans path
            if not state.get("selected_suggested_aim"):
                existing_aims = [c.get("aim", "").strip() for c in (state.get("custom_aims") or [])]
                if user_message.strip() not in existing_aims:
                    custom_aims = list(state.get("custom_aims") or [])
                    counter = len(custom_aims) + 1
                    custom_aims.append({
                        "confirm_id": f"cus-{counter}",
                        "aim": user_message.strip(),
                        "display_number": counter,
                    })
                    result["custom_aims"] = custom_aims
            return result

        result["agent_message"] = str(message or "Let me summarize what I've found and how we can proceed.").strip()
        result["phase"] = "ask"
        return result

    # If LLM says call_tool but tool name is missing/empty, treat as respond
    if action == "call_tool" and not tool:
        msg = str(message or "Let me summarize what I've found and how we can proceed.").strip()
        if state.get("analysis_proposals") or state.get("plan"):
            msg += (
                "\n\n---\n"
                "**How to proceed:**\n"
                "- ✅ **Go — proceed** if you're satisfied with this plan\n"
                "- 🔄 **More options** for fresh alternatives\n"
                "- ✏️ **Change something** to modify details of this plan"
            )
        result["agent_message"] = msg
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
                # We burned through 10 tool calls without ever resolving a
                # line/schema — almost always means extraction couldn't
                # pin down a line name from the message. Say so honestly
                # instead of the misleading "I've gathered enough
                # information" filler, and clear the stuck mention so the
                # next message gets a clean retry instead of looping again.
                line_mention = session_json.get("line", {}).get("mention")
                if line_mention:
                    result["agent_message"] = (
                        f"I couldn't resolve **{line_mention}** to a known production line. "
                        "Could you double-check the spelling, or give me the exact line name?"
                    )
                else:
                    result["agent_message"] = (
                        "I couldn't figure out which production line or machine you're asking about. "
                        "Could you tell me the exact line name (e.g. FRUITS_TEST)?"
                    )
                slots = dict(state.get("slots") or {})
                line = dict(slots.get("line") or {})
                line["mention"] = None
                slots["line"] = line
                result["slots"] = slots
                result["phase"] = "ask"
                return result
            result["tool_call_history"] = list(tool_call_history[:-1]) + [result["tool_to_call"]]
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            return result

        # Guard: confirm_plan routing (pre-check at the top of this function
        # catches the common case before the LLM; this is a safety net for
        # any path that reaches here regardless).
        if tool == "confirm_plan":
            if not state.get("analysis_proposals") and not state.get("plan"):
                result["tool_to_call"] = "generate_plans"
                result["tool_call_count"] = tool_call_count + 1
                result["phase"] = "tool"
                result["tool_call_history"] = list(tool_call_history[:-1]) + ["generate_plans"]
                return result
            return _handle_confirm(state, user_message.strip().lower(), session_json)

        # Guard: route "more options" to generate_plans instead of answer_advisory
        if tool == "answer_advisory" and any(
            phrase in user_message.lower() for phrase in ["more options", "another option", "another plan", "different options"]
        ):
            result["tool_to_call"] = "generate_plans"
            result["tool_call_count"] = tool_call_count + 1
            result["phase"] = "tool"
            result["tool_call_history"] = list(tool_call_history[:-1]) + ["generate_plans"]
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
            result["tool_call_history"] = list(tool_call_history[:-1]) + ["answer_advisory"]
            return result

        # Guard: after fetch_schema, don't generate plans if the user only
        # mentioned a line name.  The aim slot may have been spuriously
        # filled by extract_slots (e.g. "japan fruit" → aim_raw="japan fruit")
        # when the user really just named a line.  In that case respond with
        # dataset info so the suggested-aims UI cards render.
        if tool == "generate_plans" and session_json.get("schema_fetched"):
            tool_history = state.get("tool_call_history") or []
            last_tool = tool_history[-1] if tool_history else None
            if last_tool == "fetch_schema" and not state.get("selected_suggested_aim"):
                aim_raw = (session_json.get("aim", {}).get("raw") or "").strip().lower()
                line_mention = (session_json.get("line", {}).get("mention") or "").strip().lower()
                if not aim_raw or aim_raw == line_mention:
                    datasets = session_json.get("datasets") or []
                    ds_parts = []
                    for d in datasets:
                        name = d.get("name") or d.get("dataset_name") or "?"
                        cols = d.get("column_count") or len(d.get("columns") or [])
                        ds_parts.append(f"{name} ({cols} columns)")
                    ds_summary = ", ".join(ds_parts) if ds_parts else "datasets loaded"
                    line_canonical = session_json.get("line", {}).get("canonical") or ""
                    ack = ""
                    source = session_json.get("line", {}).get("source")
                    if source in ("synonym", "task_alias"):
                        mention = session_json.get("line", {}).get("mention") or ""
                        ack = f"I found that '{mention}' matches the line {line_canonical} via synonym.\n\n"
                    result["tool_to_call"] = None
                    result["tool_result"] = None
                    result["analyst_reasoning"] = None
                    result["agent_message"] = f"{ack}{ds_summary}"
                    result["phase"] = "ask"
                    return result

        # Guard: skip fetch_schema if already fetched
        if tool == "fetch_schema" and session_json.get("schema_fetched"):
            result["tool_to_call"] = "reorganize_aims" if not session_json.get("aim", {}).get("reorganized") else "generate_plans"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            result["tool_call_history"] = list(tool_call_history[:-1]) + [result["tool_to_call"]]
            return result

        # Guard: skip extract_slots if line already mentioned
        if tool == "extract_slots" and session_json.get("line", {}).get("mention"):
            result["tool_to_call"] = "resolve_line" if not session_json.get("line", {}).get("resolved") else "fetch_schema"
            result["phase"] = "tool"
            result["tool_call_count"] = tool_call_count + 1
            result["tool_call_history"] = list(tool_call_history[:-1]) + [result["tool_to_call"]]
            return result

        # Custom aim numbering: when generate_plans is called for a user-typed
        # aim (not a registry-suggested aim), assign it a display_number and
        # store it in custom_aims so it can be referenced later.
        if tool == "generate_plans" and not state.get("selected_suggested_aim"):
            existing_aims = [c.get("aim", "").strip() for c in (state.get("custom_aims") or [])]
            if user_message.strip() not in existing_aims:
                custom_aims = list(state.get("custom_aims") or [])
                counter = len(custom_aims) + 1
                custom_aims.append({
                    "confirm_id": f"cus-{counter}",
                    "aim": user_message.strip(),
                    "display_number": counter,
                })
                result["custom_aims"] = custom_aims

        result["tool_call_count"] = tool_call_count + 1
        result["phase"] = "tool"
        return result

    # Treat unrecognized/missing action as respond
        msg = str(message or "Let me summarize what I've found and how we can proceed.").strip()
        if state.get("analysis_proposals") or state.get("plan"):
            msg += (
                "\n\n---\n"
                "**How to proceed:**\n"
                "- ✅ **Go — proceed** if you're satisfied with this plan\n"
                "- 🔄 **More options** for fresh alternatives\n"
                "- ✏️ **Change something** to modify details of this plan"
            )
        result["agent_message"] = msg
        result["phase"] = "ask"
        return result
