import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


def _empty_slots():
    return {
        "line": {"mention": None, "canonical": None, "resolved": False, "source": None, "candidates": []},
        "time": {"raw": None, "start_raw": None, "end_raw": None, "mentioned": False, "start": None, "end": None, "resolved": False, "ambiguous": False, "interpretations": [], "no_filter": False, "parse_error": None, "canonical": None},
        "aim": {"raw": None, "aims": [], "reorganized": False},
        "scope": {"slot_count": 0, "intent_mode": "single", "joint_aim_raw": None, "joint_time_raw": None},
        "line_slots": [],
        "active_line_index": None,
        "dataset_context": {"by_line": {}, "active_line": None, "pending_mentions": [], "pending_exclude": [], "pending_include": []},
    }


async def tool_extract_slots(state: ManagerState) -> ManagerState:
    logger.debug("tool_extract_slots: starting")
    user_message = (state.get("user_message") or "").strip()
    current_slots = state.get("slots") or _empty_slots()

    system = load_prompt(
        "extract_slots",
        reference_now=state.get("reference_now", ""),
        session_state_json=json.dumps(
            {
                "line": current_slots.get("line"),
                "time": {
                    "raw": (current_slots.get("time") or {}).get("raw"),
                    "mentioned": (current_slots.get("time") or {}).get("mentioned"),
                    "resolved": (current_slots.get("time") or {}).get("resolved"),
                    "start": (current_slots.get("time") or {}).get("start"),
                    "end": (current_slots.get("time") or {}).get("end"),
                },
                "aim": current_slots.get("aim"),
                "line_slots": [
                    {"mention": s.get("mention"), "canonical": s.get("canonical"), "status": s.get("status")}
                    for s in (current_slots.get("line_slots") or [])
                ],
                "has_plan": bool(state.get("plan")),
                "phase": state.get("phase"),
            },
            indent=2,
        ),
        user_message=user_message,
    )

    llm = get_llm_client()
    try:
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user_message)],
            caller="extract_slots",
        )
    except Exception:
        logger.exception("extract_slots: LLM failed")
        return {**state, "error": "tool_failed", "tool_result": json.dumps({"error": "llm_failed"})}

    try:
        extracted = parse_json_from_message(response.content or "{}")
    except (json.JSONDecodeError, TypeError):
        extracted = {}

    merged = dict(current_slots)
    if extracted.get("line_mention"):
        merged["line"]["mention"] = str(extracted["line_mention"]).strip()
    if extracted.get("time_raw"):
        merged["time"]["raw"] = str(extracted["time_raw"]).strip()
        merged["time"]["mentioned"] = True
        merged["time"]["resolved"] = False
        merged["time"]["ambiguous"] = False
    if extracted.get("aim_raw"):
        existing_aims = merged["aim"].get("aims", [])
        new_aim = str(extracted["aim_raw"]).strip()
        if new_aim and new_aim not in existing_aims:
            merged["aim"]["aims"] = existing_aims + [new_aim]
        merged["aim"]["raw"] = (merged["aim"].get("raw") or "") + (" " + new_aim if merged["aim"].get("raw") else "")
        merged["aim"]["reorganized"] = False
    if extracted.get("line_mentions"):
        merged["line_slots"] = [
            {"mention": m.strip(), "status": "pending", "resolved": False}
            for m in extracted["line_mentions"]
            if m.strip()
        ]

    scope = extracted.get("scope")
    if isinstance(scope, dict) and scope.get("intent_mode"):
        merged["scope"]["intent_mode"] = scope["intent_mode"]

    return {
        **state,
        "slots": merged,
        "tool_result": json.dumps({"extracted": extracted, "merged_slots": merged}),
        "phase": "tool",
    }
