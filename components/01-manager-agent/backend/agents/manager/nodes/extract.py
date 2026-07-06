import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.chat_memory import get_recent_chat_messages
from agents.manager.debug_log import debug, debug_state
from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt
from agents.manager.registry_context import merge_dataset_intent_from_clarification
from agents.manager.scope_selection import (
    apply_scope_selection,
    parse_scope_reply,
    set_scope_pending_for_propose,
)
from agents.manager.slot_inventory import (
    _SKIP_AIM_PHRASES,
    apply_clarification,
    build_line_slots_from_extraction,
    empty_aim_exploration,
    parse_clarification_extras,
    parse_reuse_intent,
    parse_session_intent,
)
from agents.manager.slots import compute_missing, session_state_for_llm
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)

_EXPLORE_ACTIONS = frozenset(
    {"propose", "refine", "save", "combine_saved", "activate", "list_saved", "confirm", "select"}
)





def _merge_extraction(slots: dict, extracted: dict) -> dict:

    merged = {

        "line": dict(slots.get("line") or {}),

        "time": dict(slots.get("time") or {}),

        "aim": dict(slots.get("aim") or {}),

        "scope": dict(slots.get("scope") or {}),

        "line_slots": list(slots.get("line_slots") or []),

        "active_line_index": slots.get("active_line_index"),

        "dataset_context": dict(slots.get("dataset_context") or {}),

    }



    clarification = extracted.get("clarification") or {}

    if isinstance(clarification, dict) and clarification.get("intent_mode"):

        scope = dict(merged.get("scope") or {})

        scope["intent_mode"] = clarification["intent_mode"]

        merged["scope"] = scope



    merged = build_line_slots_from_extraction(merged, extracted)



    line_mention = extracted.get("line_mention")

    if line_mention and not merged.get("line_slots"):

        merged["line"]["mention"] = line_mention.strip()

        if merged["line"].get("canonical") and merged["line"]["canonical"] != line_mention:

            prev = merged["line"]["canonical"]

            if line_mention.lower() not in (prev.lower(), (merged["line"].get("mention") or "").lower()):

                merged["line"]["resolved"] = False

                merged["line"]["canonical"] = None

                merged["line"]["source"] = None

                merged["line"]["candidates"] = []



    scope = merged.get("scope") or {}

    joint_time = scope.get("joint_time_raw")

    time_raw = extracted.get("time_raw") or joint_time

    time_start = extracted.get("time_start_raw")

    time_end = extracted.get("time_end_raw")

    if time_raw:

        merged["time"]["raw"] = time_raw.strip()

        merged["time"]["mentioned"] = True

        merged["time"]["start_raw"] = None

        merged["time"]["end_raw"] = None

        merged["time"]["start"] = None

        merged["time"]["end"] = None

        merged["time"]["resolved"] = False

        merged["time"]["ambiguous"] = False

        merged["time"]["interpretations"] = []

        merged["time"]["no_filter"] = False

        merged["time"]["parse_error"] = None

        merged["time"]["canonical"] = None

    elif time_start and time_end:

        merged["time"]["raw"] = f"{time_start.strip()} to {time_end.strip()}"

        merged["time"]["mentioned"] = True

        merged["time"]["start_raw"] = time_start.strip()

        merged["time"]["end_raw"] = time_end.strip()

        merged["time"]["start"] = None

        merged["time"]["end"] = None

        merged["time"]["resolved"] = False

        merged["time"]["ambiguous"] = False

        merged["time"]["interpretations"] = []

        merged["time"]["no_filter"] = False

        merged["time"]["parse_error"] = None

        merged["time"]["canonical"] = None



    aim_raw = extracted.get("aim_raw") or scope.get("joint_aim_raw")

    if aim_raw and aim_raw.lower().strip() not in _SKIP_AIM_PHRASES:

        merged["aim"]["raw"] = aim_raw.strip()

        merged["aim"]["reorganized"] = False



    active_line = (merged.get("line") or {}).get("canonical")

    merged["dataset_context"] = merge_dataset_intent_from_clarification(

        merged.get("dataset_context"),

        clarification if isinstance(clarification, dict) else extracted.get("clarification"),

        active_line,

    )



    return merged





def _merge_column_wishes(existing: list[dict] | None, new_names: list[str]) -> list[dict]:

    wishes = [dict(w) for w in (existing or []) if isinstance(w, dict)]

    known = {(w.get("name") or "").lower() for w in wishes}

    for name in new_names:

        key = name.lower()

        if key and key not in known:

            wishes.append({"name": name, "source": "user_or_advisory"})

            known.add(key)

    return wishes





async def extract_slots(state: ManagerState) -> ManagerState:

    debug_state("extract_slots", state)

    user_message = (state.get("user_message") or "").strip()

    if not user_message:

        return {**state, "phase": "extract"}



    slots = state.get("slots") or {}



    system = load_prompt(

        "extract_slots",

        reference_now=state.get("reference_now", ""),

        session_state_json=json.dumps(

            session_state_for_llm(

                slots,

                phase=state.get("phase", ""),

                explore_phase=state.get("explore_phase"),

                analysis_proposals=state.get("analysis_proposals"),

                has_plan=bool(state.get("plan")),

                state=state,

            ),

            indent=2,

        ),

        user_message=user_message,

    )

    debug("extract_slots", "calling LLM", user_message=user_message)

    messages = [SystemMessage(content=system)]
    messages.extend(get_recent_chat_messages(state.get("chat_history")))
    messages.append(HumanMessage(content=user_message))

    llm = get_llm_client()
    response = await llm.ainvoke(messages, caller="extract_slots")

    try:

        extracted = parse_json_from_message(response.content or "{}")

    except (json.JSONDecodeError, TypeError):

        extracted = {}



    debug("extract_slots", "LLM extracted", **extracted)

    clarification = extracted.get("clarification")

    slots, suggested_aims, aim_exploration, reject_plan = apply_clarification(

        user_message, slots, clarification

    )

    merged = _merge_extraction(slots, extracted)

    extras = parse_clarification_extras(clarification if isinstance(clarification, dict) else None)

    session_intent = parse_session_intent(clarification, user_message, merged)

    reuse_alias = parse_reuse_intent(clarification)



    scope_selection = state.get("scope_selection")

    scope_pending = bool(state.get("scope_pending"))

    if extras.get("scope_selection"):

        scope_selection = extras["scope_selection"]

        merged = apply_scope_selection(merged, scope_selection)

        scope_pending = False

    elif scope_pending:

        reply = parse_scope_reply(user_message, merged)

        if reply:

            scope_selection = reply

            merged = apply_scope_selection(merged, reply)

            scope_pending = False

            if not aim_exploration.get("action"):

                prior = (state.get("aim_exploration") or {}).get("action")

                if prior in ("propose", "refine"):

                    aim_exploration = dict(state.get("aim_exploration") or empty_aim_exploration())



    user_explore_intent = state.get("user_explore_intent")

    if extras.get("user_explore_intent"):

        user_explore_intent = extras["user_explore_intent"]

    elif user_message.lower().strip() == "generate":

        user_explore_intent = None



    session_goal = state.get("session_goal")

    if extras.get("session_goal"):

        session_goal = extras["session_goal"]



    iot_column_wishes = _merge_column_wishes(

        state.get("iot_column_wishes"),

        extras.get("column_wishes") or [],

    )



    explore_action = (aim_exploration or {}).get("action")

    if session_intent == "advisory":

        aim_exploration = empty_aim_exploration()

        suggested_aims = False

        prev_aim = (state.get("slots") or {}).get("aim") or {}

        if prev_aim.get("raw") or prev_aim.get("aims"):

            merged["aim"] = dict(prev_aim)

    elif explore_action not in _EXPLORE_ACTIONS and (merged.get("aim") or {}).get("raw"):

        aim_exploration = empty_aim_exploration()

        suggested_aims = False



    if explore_action in ("propose", "refine"):

        merged["registry_sync_target"] = None



    result = {

        **state,

        "slots": merged,

        "missing": compute_missing(merged),

        "phase": "extract",

        "task_confirmed": False,

        "wants_suggested_aims": suggested_aims,

        "aim_exploration": aim_exploration,

        "dataset_context": merged.get("dataset_context"),

        "session_intent": session_intent,

        "reuse_alias": reuse_alias,

        "scope_selection": scope_selection,

        "scope_pending": scope_pending,

        "user_explore_intent": user_explore_intent,

        "session_goal": session_goal,

        "iot_column_wishes": iot_column_wishes,

        "saved_plans": state.get("saved_plans") or [],

    }

    if reject_plan:

        result["plan"] = None

        result["analysis_proposals"] = None

        result["explore_phase"] = None

        aim_slot = dict(merged.get("aim") or {})

        aim_slot["aims"] = []

        aim_slot["raw"] = None

        aim_slot["reorganized"] = False

        merged["aim"] = aim_slot

        result["slots"] = merged

        result["missing"] = compute_missing(merged)

    if session_intent == "advisory":
        result["registry_sync_target"] = None
    if explore_action in ("propose", "refine", "save", "combine_saved", "activate", "list_saved"):
        result["registry_sync_target"] = None
    result = set_scope_pending_for_propose(result)

    debug_state("extract_slots", result)

    return result





async def merge_slots(state: ManagerState) -> ManagerState:

    debug_state("merge_slots", state)

    slots = state.get("slots") or {}

    result = {**state, "missing": compute_missing(slots)}

    debug("merge_slots", "done", missing=result["missing"])

    return result


