"""Slot helpers for the manager agent slot-filling pipeline."""

from agents.manager.registry_context import build_context_inventory, empty_dataset_context


def empty_line_slot(mention: str = "") -> dict:
    return {
        "mention": mention,
        "canonical": None,
        "resolved": False,
        "source": None,
        "candidates": [],
        "status": "pending",
        "aim_raw": None,
        "time_raw": None,
        "skipped": False,
        "lookup_locked": False,
    }


def empty_scope() -> dict:
    return {
        "slot_count": 0,
        "intent_mode": "single",
        "joint_aim_raw": None,
        "joint_time_raw": None,
    }


def empty_slots() -> dict:
    return {
        "line": {
            "mention": None,
            "canonical": None,
            "resolved": False,
            "source": None,
            "candidates": [],
        },
        "time": {
            "raw": None,
            "start_raw": None,
            "end_raw": None,
            "mentioned": False,
            "start": None,
            "end": None,
            "resolved": False,
            "ambiguous": False,
            "interpretations": [],
            "no_filter": False,
            "parse_error": None,
            "canonical": None,
        },
        "aim": {"raw": None, "aims": [], "reorganized": False},
        "scope": empty_scope(),
        "line_slots": [],
        "active_line_index": None,
        "dataset_context": empty_dataset_context(),
    }


def compute_missing(slots: dict) -> list[str]:
    missing: list[str] = []
    if not slots["line"].get("resolved"):
        missing.append("line")
    aim = slots.get("aim") or {}
    if not aim.get("raw") and not aim.get("aims"):
        missing.append("aim")
    return missing


def time_needs_clarification(slots: dict) -> bool:
    time = slots.get("time") or {}
    if not time.get("mentioned"):
        return False
    if time.get("no_filter"):
        return False
    if time.get("ambiguous"):
        return True
    if time.get("raw") and not time.get("resolved"):
        return True
    return False




def session_state_for_llm(
    slots: dict,
    *,
    phase: str = "",
    explore_phase: str | None = None,
    analysis_proposals: list[dict] | None = None,
    has_plan: bool = False,
    state: dict | None = None,
) -> dict:
    line = slots.get("line") or {}
    time = slots.get("time") or {}
    aim = slots.get("aim") or {}
    scope = slots.get("scope") or {}
    line_slots = slots.get("line_slots") or []
    proposal_summary = [
        {"id": p.get("id"), "title": p.get("title")}
        for p in (analysis_proposals or [])
        if isinstance(p, dict)
    ]
    dataset_context = slots.get("dataset_context") or empty_dataset_context()
    inventory = build_context_inventory(dataset_context, slots=slots)

    session_inventory = None
    if state:
        session_inventory = state.get("session_inventory")
        if not session_inventory:
            from agents.manager.context.session_inventory import build_session_inventory

            session_inventory = build_session_inventory({**state, "slots": slots})

    result = {
        "line_slots": [
            {
                "mention": s.get("mention"),
                "canonical": s.get("canonical"),
                "status": s.get("status"),
                "lookup_locked": s.get("lookup_locked", False),
                "skipped": s.get("skipped", False),
                "source": s.get("source"),
            }
            for s in line_slots
        ],
        "active_line_index": slots.get("active_line_index"),
        "intent_mode": scope.get("intent_mode"),
        "line_mention": line.get("mention"),
        "line_canonical": line.get("canonical"),
        "time": {
            "raw": time.get("raw"),
            "mentioned": time.get("mentioned"),
            "resolved": time.get("resolved"),
            "no_filter": time.get("no_filter"),
            "start": time.get("start"),
            "end": time.get("end"),
        },
        "aim": {"raw": aim.get("raw"), "aims": aim.get("aims")},
        "phase": phase,
        "explore_phase": explore_phase,
        "analysis_proposals": proposal_summary,
        "has_plan": has_plan,
        "dataset_context": inventory,
        "included_datasets": inventory.get("included_datasets") or [],
        "excluded_datasets": inventory.get("excluded_datasets") or [],
        "available_datasets": inventory.get("available_datasets") or [],
        "active_line": inventory.get("active_line"),
    }
    if session_inventory:
        result["session_inventory"] = session_inventory
    if state:
        saved = state.get("saved_plans") or []
        if saved:
            result["saved_plans"] = [
                {"id": p.get("id"), "title": p.get("title")}
                for p in saved
                if isinstance(p, dict)
            ]
        if state.get("scope_selection"):
            result["scope_selection"] = state.get("scope_selection")
        if state.get("scope_pending"):
            result["scope_pending"] = True
        if state.get("session_goal"):
            result["session_goal"] = state.get("session_goal")
    return result
