"""Time Context Service — inventory and intent merge for slots.time."""

from __future__ import annotations

from copy import deepcopy

from agents.manager.slots import time_needs_clarification


def build_time_inventory(slots: dict | None) -> dict:
    time = (slots or {}).get("time") or {}
    mentioned = bool(time.get("mentioned") or time.get("raw"))
    no_filter = bool(time.get("no_filter"))
    resolved = bool(time.get("resolved"))
    return {
        "mentioned": mentioned,
        "raw": time.get("raw"),
        "start": time.get("start"),
        "end": time.get("end"),
        "no_filter": no_filter,
        "resolved": resolved,
        "ambiguous": bool(time.get("ambiguous")),
        "needs_clarification": time_needs_clarification(slots or {}),
        "optional": True,
        "required_for_plan": False,
        "status": _time_status(time, slots or {}),
    }


def _time_status(time: dict, slots: dict) -> str:
    if not time.get("mentioned") and not time.get("raw"):
        return "not_specified"
    if time.get("no_filter"):
        return "all_data"
    if time.get("ambiguous"):
        return "ambiguous"
    if time.get("resolved") and time.get("start"):
        return "resolved"
    if time.get("raw") and not time.get("resolved"):
        return "pending"
    if time.get("parse_error"):
        return "error"
    return "not_specified"


def merge_time_intent_from_clarification(clarification: dict | None, slots: dict) -> dict:
    """Apply clarification.time_intent to slots.time."""
    slots = deepcopy(slots)
    time_slot = dict(slots.get("time") or {})
    clar = clarification or {}
    intent = clar.get("time_intent")
    if not intent or not isinstance(intent, dict):
        return slots

    action = (intent.get("action") or "").strip().lower()
    phrase = intent.get("phrase")

    if action == "no_filter" or action == "clear_filter":
        time_slot["no_filter"] = True
        time_slot["resolved"] = True
        time_slot["ambiguous"] = False
        time_slot["start"] = None
        time_slot["end"] = None
        time_slot["parse_error"] = None
    elif action == "set_phrase" and phrase:
        time_slot["raw"] = str(phrase).strip()
        time_slot["mentioned"] = True
        time_slot["resolved"] = False
        time_slot["no_filter"] = False
        time_slot["ambiguous"] = False
        time_slot["start"] = None
        time_slot["end"] = None
        time_slot["parse_error"] = None

    slots["time"] = time_slot
    return slots


def format_time_for_prompt(inventory: dict | None) -> str:
    inv = inventory or {}
    status = inv.get("status") or "not_specified"
    if status == "not_specified":
        return "Time: not specified (optional — all data if omitted)"
    if status == "all_data":
        return "Time: no date filter (all available data)"
    if status == "resolved":
        raw = inv.get("raw") or ""
        note = f' (from "{raw}")' if raw else ""
        return f"Time: {inv.get('start')} → {inv.get('end')}{note}"
    if status == "ambiguous":
        return f"Time: ambiguous — needs clarification ({inv.get('raw') or '?'})"
    if status == "pending":
        return f"Time: pending resolution ({inv.get('raw')})"
    return f"Time: {status}"
