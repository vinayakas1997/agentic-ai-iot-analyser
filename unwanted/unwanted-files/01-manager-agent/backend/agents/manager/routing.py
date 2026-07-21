from agents.manager.debug_log import debug_route
from agents.manager.scope_selection import needs_scope_prompt
from agents.manager.slot_inventory import compute_multi_missing
from agents.manager.slots import compute_missing, time_needs_clarification
from agents.manager.state import ManagerState



_CONFIRM_WORDS = ("go", "confirm", "yes", "proceed", "ok")





def is_confirm_message(state: ManagerState) -> bool:

    if state.get("phase") != "plan":

        return False

    user_msg = (state.get("user_message") or "").lower().strip()

    return user_msg in _CONFIRM_WORDS


def is_confirm_like_message(state: ManagerState) -> bool:

    if state.get("phase") != "plan":

        return False

    user_msg = (state.get("user_message") or "").lower().strip()

    return any(word in user_msg.split() for word in _CONFIRM_WORDS)





def _explore_action(state: ManagerState) -> str | None:

    action = (state.get("aim_exploration") or {}).get("action")

    if action in (
        "confirm",
        "select",
        "propose",
        "refine",
        "save",
        "combine_saved",
        "activate",
        "list_saved",
    ):

        return action

    return None





def _route_explore(state: ManagerState) -> str | None:

    action = _explore_action(state)

    if not action:

        return None

    if action == "save":

        debug_route("_route_explore", "save_to_shortlist")

        return "save_to_shortlist"

    if action == "list_saved":

        debug_route("_route_explore", "list_saved_plans")

        return "list_saved_plans"

    if action == "activate":

        debug_route("_route_explore", "activate_saved_plan")

        return "activate_saved_plan"

    if action == "combine_saved":

        debug_route("_route_explore", "combine_saved_plans")

        return "combine_saved_plans"

    if action in ("propose", "refine") and needs_scope_prompt(state):

        debug_route("_route_explore", "ask_scope_selection")

        return "ask_scope_selection"

    if action in ("confirm", "select") and state.get("analysis_proposals"):

        debug_route("_route_explore", "merge_proposals_to_plan")

        return "merge_proposals_to_plan"

    if action in ("propose", "refine", "confirm", "select"):

        debug_route("_route_explore", "propose_or_refine_plans")

        return "propose_or_refine_plans"

    return None





def _line_resolved(state: ManagerState) -> bool:

    slots = state.get("slots") or {}

    line = slots.get("line") or {}

    if line.get("resolved"):

        return True

    for s in slots.get("line_slots") or []:

        if s.get("status") == "resolved" and not s.get("skipped"):

            return True

    return False





def _needs_sync_session(state: ManagerState) -> bool:

    if not _line_resolved(state):

        return False

    explore_route = _route_explore(state)

    if explore_route:

        return explore_route == "propose_or_refine_plans"

    return True





def _route_after_sync_common(state: ManagerState) -> str:

    if state.get("registry_sync_target") == "reorganize":

        debug_route("route_after_sync_session_context", "reorganize_aim")

        return "reorganize_aim"



    if state.get("error") == "no_datasets":

        debug_route("route_after_sync_session_context", "__end__")

        return "__end__"



    slots = state.get("slots") or {}

    line = slots.get("line") or {}



    explore_route = _route_explore(state)

    if explore_route:

        debug_route("route_after_sync_session_context", explore_route)

        return explore_route



    if state.get("wants_suggested_aims") and line.get("resolved"):

        debug_route("route_after_sync_session_context", "show_suggested_aims")

        return "show_suggested_aims"



    multi_missing = compute_multi_missing(slots)

    if multi_missing.needs_any_clarification:

        debug_route("route_after_sync_session_context", "ask_multi_missing")

        return "ask_multi_missing"



    if state.get("error") == "line_not_found":

        debug_route("route_after_sync_session_context", "line_not_found")

        return "line_not_found"



    if state.get("error") == "line_ambiguous":

        debug_route("route_after_sync_session_context", "ask_line_ambiguous")

        return "ask_line_ambiguous"



    if line.get("resolved") and state.get("line_context"):

        debug_route("route_after_sync_session_context", "resolve_time_filters")

        return "resolve_time_filters"



    debug_route("route_after_sync_session_context", "ask_missing")

    return "ask_missing"





def route_after_inject(state: ManagerState) -> str:

    if is_confirm_message(state):

        debug_route("route_after_inject", "detect_confirm")

        return "detect_confirm"

    if is_confirm_like_message(state):

        debug_route("route_after_inject", "confirm_redirect")

        return "confirm_redirect"

    debug_route("route_after_inject", "analyze_conversational")

    return "analyze_conversational"





def route_after_conversational(state: ManagerState) -> str:

    intent = (state.get("conversational_intent") or "extract").strip().lower()

    if intent == "converse":

        debug_route("route_after_conversational", "__end__ (converse)")

        return "__end__"

    debug_route("route_after_conversational", "extract_slots")

    return "extract_slots"


def route_after_merge(state: ManagerState) -> str:

    debug_route("route_after_merge", "resolve_all_lines")

    return "resolve_all_lines"





def route_after_resolve_all_lines(state: ManagerState) -> str:

    slots = state.get("slots") or {}

    line_slots = slots.get("line_slots") or []



    explore_route = _route_explore(state)

    if explore_route == "merge_proposals_to_plan":

        debug_route("route_after_resolve_all_lines", explore_route)

        return explore_route



    if _needs_sync_session(state):

        debug_route("route_after_resolve_all_lines", "sync_session_context")

        return "sync_session_context"



    if state.get("wants_suggested_aims") and (state.get("slots") or {}).get("line", {}).get("resolved"):

        if state.get("line_context"):

            debug_route("route_after_resolve_all_lines", "show_suggested_aims")

            return "show_suggested_aims"



    multi_missing = compute_multi_missing(slots)

    if multi_missing.needs_any_clarification:

        debug_route("route_after_resolve_all_lines", "ask_multi_missing")

        return "ask_multi_missing"



    if state.get("error") == "line_not_found" and len(line_slots) <= 1:

        debug_route("route_after_resolve_all_lines", "line_not_found")

        return "line_not_found"



    if state.get("error") == "line_ambiguous" and len(line_slots) <= 1:

        debug_route("route_after_resolve_all_lines", "ask_line_ambiguous")

        return "ask_line_ambiguous"



    debug_route("route_after_resolve_all_lines", "ask_missing")

    return "ask_missing"





def route_after_sync_session_context(state: ManagerState) -> str:

    if state.get("reuse_alias"):

        debug_route("route_after_sync_session_context", "apply_task_reuse")

        return "apply_task_reuse"



    slots = state.get("slots") or {}

    line = slots.get("line") or {}



    if (
        state.get("session_intent") == "advisory"
        and line.get("resolved")
        and state.get("line_context")
    ):

        debug_route("route_after_sync_session_context", "answer_advisory")

        return "answer_advisory"



    if state.get("session_intent") == "meta_question":

        debug_route("route_after_sync_session_context", "answer_session_meta")

        return "answer_session_meta"



    return _route_after_sync_common(state)








def route_after_time(state: ManagerState) -> str:

    slots = state.get("slots") or {}

    if time_needs_clarification(slots):

        debug_route("route_after_time", "ask_time_ambiguous")

        return "ask_time_ambiguous"

    if state.get("missing"):

        debug_route("route_after_time", "ask_missing")

        return "ask_missing"

    debug_route("route_after_time", "sync_session_context")

    return "sync_session_context"





def route_after_confirm(state: ManagerState) -> str:

    if state.get("task_confirmed"):

        debug_route("route_after_confirm", "save_task_definition")

        return "save_task_definition"

    debug_route("route_after_confirm", "extract_slots")

    return "extract_slots"

