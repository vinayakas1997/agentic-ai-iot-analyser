from datetime import datetime, timezone




from agents.manager.debug_log import debug, debug_state

from agents.manager.slots import compute_missing, time_needs_clarification

from agents.manager.state import ManagerState

from agents.manager.time_resolution import apply_result_to_time_slot, resolve_time_phrase





def inject_reference_time(state: ManagerState) -> ManagerState:

    debug_state("inject_reference_time", state)

    now = datetime.now(timezone.utc)

    result = {

        **state,

        "reference_now": now.isoformat(),

        "reference_timezone": state.get("reference_timezone") or "UTC",

    }

    debug("inject_reference_time", "done", reference_now=result["reference_now"])

    return result





async def resolve_time_filters(state: ManagerState) -> ManagerState:

    debug_state("resolve_time_filters", state)

    slots = dict(state.get("slots") or {})

    time_slot = dict(slots.get("time") or {})

    raw = (time_slot.get("raw") or "").strip()



    if not raw and not (time_slot.get("start_raw") and time_slot.get("end_raw")):

        time_slot["resolved"] = True

        time_slot["no_filter"] = True

        time_slot["ambiguous"] = False

        time_slot["interpretations"] = []

        time_slot["parse_error"] = None

        time_slot["start"] = None

        time_slot["end"] = None

    else:

        phrase = raw or f"{time_slot.get('start_raw')} to {time_slot.get('end_raw')}"

        if not raw and time_slot.get("start_raw"):

            time_slot["raw"] = phrase

            time_slot["mentioned"] = True



        result = await resolve_time_phrase(phrase, state["reference_now"])

        debug("resolve_time_filters", "resolve_time_phrase result", result=result)

        time_slot = apply_result_to_time_slot(time_slot, result)



    slots["time"] = time_slot

    result_state = {**state, "slots": slots, "missing": compute_missing(slots)}

    if not time_needs_clarification(slots) and not compute_missing(slots):
        result_state["registry_sync_target"] = "reorganize"

    debug(

        "resolve_time_filters",

        "done",

        raw=time_slot.get("raw"),

        start=time_slot.get("start"),

        end=time_slot.get("end"),

        resolved=time_slot.get("resolved"),

        no_filter=time_slot.get("no_filter"),

        ambiguous=time_slot.get("ambiguous"),

        needs_clarification=time_needs_clarification(slots),

        missing=result_state["missing"],

    )

    return result_state


