"""Multi-slot inventory, question planning, and clarification helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agents.manager.constants import SOURCE_LABELS
from agents.manager.registry_context import merge_dataset_intent_from_clarification
from agents.manager.context.time import merge_time_intent_from_clarification
from agents.manager.prompt_hints import format_aim_missing_hint
from agents.manager.slots import empty_line_slot, empty_scope

_SKIP_AIM_PHRASES = frozenset(
    {
        "tell me about",
        "leave",
        "skip",
        "ignore",
        "drop",
        "continue with",
    }
)

_SUGGESTED_AIMS_PATTERNS = (
    "what aims",
    "suggested aim",
    "what can we do",
    "what can we analyze",
    "what analysis",
    "show aims",
    "options for",
    "aims that we",
    "aims we can",
    "aims can we",
)


@dataclass
class MultiMissing:
    needs_any_clarification: bool = False
    not_found_slots: list[dict] = field(default_factory=list)
    ambiguous_slots: list[dict] = field(default_factory=list)
    unclear_intent: bool = False
    missing_aim: bool = False
    needs_active_line_choice: bool = False


def normalize_mention(text: str) -> str:
    return re.sub(r"[_\-]+", " ", (text or "").lower().strip())


def match_mention_to_existing(mention: str, line_slots: list[dict]) -> int | None:
    """Fuzzy-match a mention to an existing line slot index."""
    norm = normalize_mention(mention)
    if not norm:
        return None
    for i, slot in enumerate(line_slots):
        sm = normalize_mention(slot.get("mention") or "")
        sc = normalize_mention(slot.get("canonical") or "")
        if norm == sm or norm == sc:
            return i
        if sm and (norm in sm or sm in norm):
            return i
        if sc and (norm in sc or sc in norm):
            return i
    return None


def wants_suggested_aims(user_message: str) -> bool:
    text = user_message.lower()
    return any(p in text for p in _SUGGESTED_AIMS_PATTERNS)


def _line_slots(slots: dict) -> list[dict]:
    return list(slots.get("line_slots") or [])


def _scope(slots: dict) -> dict:
    return slots.get("scope") or empty_scope()


def _resolved_slots(slots: dict) -> list[tuple[int, dict]]:
    return [
        (i, s)
        for i, s in enumerate(_line_slots(slots))
        if s.get("status") == "resolved" and not s.get("skipped")
    ]


def sync_active_line(slots: dict, index: int | None = None) -> dict:
    """Copy the chosen line slot into legacy slots['line'] for plan/planner."""
    slots = dict(slots)
    line_slots = list(slots.get("line_slots") or [])
    idx = index if index is not None else slots.get("active_line_index")
    if idx is None or idx < 0 or idx >= len(line_slots):
        return slots

    chosen = line_slots[idx]
    slots["line"] = {
        "mention": chosen.get("mention"),
        "canonical": chosen.get("canonical"),
        "resolved": chosen.get("resolved", False),
        "source": chosen.get("source"),
        "candidates": list(chosen.get("candidates") or []),
    }
    slots["active_line_index"] = idx
    return slots


def auto_select_active_line(slots: dict) -> dict:
    """Auto-select when there is exactly one non-skipped resolved slot and no blocking not-found slots."""
    slots = dict(slots)
    if slots.get("active_line_index") is not None:
        return sync_active_line(slots)

    line_slots = _line_slots(slots)
    resolved = _resolved_slots(slots)
    not_found = [s for s in line_slots if s.get("status") == "not_found" and not s.get("skipped")]

    if len(line_slots) == 1 and resolved:
        slots["active_line_index"] = resolved[0][0]
        return sync_active_line(slots)
    if len(resolved) == 1 and not not_found:
        slots["active_line_index"] = resolved[0][0]
        return sync_active_line(slots)
    return slots


def _slot_status_label(slot: dict) -> str:
    status = slot.get("status")
    mention = slot.get("mention") or "?"
    if status == "resolved":
        canonical = slot.get("canonical") or mention
        source = slot.get("source")
        label = SOURCE_LABELS.get(source, source or "match")
        return f"**{mention}** → **{canonical}** (matched via {label})"
    if status == "not_found":
        return f"**{mention}** → not found in the IoT catalog"
    if status == "ambiguous":
        candidates = ", ".join(f"**{c}**" for c in slot.get("candidates") or [])
        return f"**{mention}** → ambiguous ({candidates})"
    if slot.get("skipped"):
        return f"**{mention}** → skipped"
    return f"**{mention}** → pending"


def format_slot_summary(slots: dict) -> str:
    line_slots = _line_slots(slots)
    if not line_slots:
        return ""

    count = len(line_slots)
    lines = [f"I found **{count} machine{'s' if count != 1 else ''}** in your request:", ""]
    for i, slot in enumerate(line_slots, start=1):
        lines.append(f"{i}. {_slot_status_label(slot)}")

    scope = _scope(slots)
    time_slot = slots.get("time") or {}
    aim = slots.get("aim") or {}

    lines.append("")
    if time_slot.get("no_filter") or (time_slot.get("resolved") and not time_slot.get("raw")):
        lines.append("**Time:** no date filter (all available data)")
    elif time_slot.get("resolved") and time_slot.get("start"):
        raw = time_slot.get("raw") or ""
        note = f' (from "{raw}")' if raw else ""
        lines.append(f"**Time:** {time_slot.get('start')} → {time_slot.get('end')}{note}")
    elif scope.get("joint_time_raw"):
        lines.append(f"**Time:** {scope['joint_time_raw']} (not yet resolved)")
    else:
        lines.append("**Time:** not specified")

    joint_aim = scope.get("joint_aim_raw")
    aim_raw = aim.get("raw")
    if aim_raw or (joint_aim and joint_aim.lower() not in _SKIP_AIM_PHRASES):
        lines.append(f"**Analysis:** {aim_raw or joint_aim}")
    else:
        per_slot_aims = [s.get("aim_raw") for s in line_slots if s.get("aim_raw")]
        if per_slot_aims:
            lines.append("**Analysis:** per-machine aims specified")
        else:
            lines.append("**Analysis:** not specified yet")

    return "\n".join(lines)


def compute_multi_missing(slots: dict) -> MultiMissing:
    line_slots = _line_slots(slots)
    scope = _scope(slots)
    result = MultiMissing()

    if not line_slots:
        return result

    result.not_found_slots = [s for s in line_slots if s.get("status") == "not_found" and not s.get("skipped")]
    result.ambiguous_slots = [s for s in line_slots if s.get("status") == "ambiguous"]
    resolved = _resolved_slots(slots)

    if scope.get("intent_mode") == "unclear" and len(line_slots) > 1:
        result.unclear_intent = True

    aim = slots.get("aim") or {}
    has_aim = bool(aim.get("raw") or aim.get("aims"))
    joint_aim = scope.get("joint_aim_raw") or ""
    has_joint_aim = bool(joint_aim) and joint_aim.lower() not in _SKIP_AIM_PHRASES
    has_per_slot_aim = any(s.get("aim_raw") for s in line_slots)
    result.missing_aim = not (has_aim or has_joint_aim or has_per_slot_aim)

    active_idx = slots.get("active_line_index")
    if len(resolved) > 1 and active_idx is None:
        result.needs_active_line_choice = True

    if result.ambiguous_slots:
        result.needs_any_clarification = True
    elif result.not_found_slots and resolved and active_idx is None:
        result.needs_any_clarification = True
    elif result.needs_active_line_choice:
        result.needs_any_clarification = True
    elif len(line_slots) > 1 and not resolved and result.not_found_slots:
        result.needs_any_clarification = True

    return result


def prepare_questions(slots: dict, missing: MultiMissing) -> list[dict]:
    questions: list[dict] = []
    line_slots = _line_slots(slots)
    resolved = _resolved_slots(slots)
    resolved_names = ", ".join(f"**{s.get('mention')}**" for _, s in resolved)

    for slot in missing.ambiguous_slots:
        mention = slot.get("mention") or "that name"
        candidates = ", ".join(f"**{c}**" for c in slot.get("candidates") or [])
        questions.append(
            {
                "id": f"ambiguous_{mention}",
                "text": f'Multiple lines match **"{mention}"**: {candidates}. Which exact line did you mean?',
            }
        )

    for slot in missing.not_found_slots:
        mention = slot.get("mention") or "that machine"
        if resolved:
            questions.append(
                {
                    "id": f"not_found_{mention}",
                    "text": (
                        f"**{mention}** isn't registered. Continue with {resolved_names} only, "
                        f"or try another name for **{mention}**?"
                    ),
                }
            )
        else:
            questions.append(
                {
                    "id": f"not_found_{mention}",
                    "text": (
                        f"**{mention}** isn't registered in the IoT catalog. "
                        "Please contact the IoT team or try another name."
                    ),
                }
            )

    if missing.needs_active_line_choice:
        options = ", ".join(f"**{s.get('mention')}**" for _, s in resolved)
        questions.append(
            {
                "id": "pick_active_line",
                "text": f"Which machine should we analyze first? Options: {options}.",
            }
        )

    if missing.unclear_intent:
        questions.append(
            {
                "id": "intent_mode",
                "text": (
                    "Do you want **one analysis applied to all machines** (e.g. compare or same metric), "
                    "or **different analyses per machine**?"
                ),
            }
        )

    if missing.missing_aim:
        aim_line_name: str | None = None
        if len(line_slots) == 1:
            slot = line_slots[0]
            if slot.get("status") == "resolved" and not slot.get("skipped"):
                aim_line_name = (slot.get("canonical") or slot.get("mention") or "").strip() or None
        aim_hint = format_aim_missing_hint(aim_line_name)
        question_id = "missing_aim_joint" if len(line_slots) > 1 else "missing_aim"
        questions.append({"id": question_id, "text": aim_hint})

    for i, slot in enumerate(line_slots):
        if slot.get("aim_raw") and not slots.get("aim", {}).get("raw"):
            mention = slot.get("mention") or f"machine {i + 1}"
            questions.append(
                {
                    "id": f"per_slot_aim_{mention}",
                    "text": f'For **{mention}**, confirm analysis: {slot["aim_raw"]}',
                }
            )

    return questions


def format_questions(questions: list[dict]) -> str:
    if not questions:
        return ""
    lines = ["", "Questions:"]
    for i, q in enumerate(questions, start=1):
        lines.append(f"{i}. {q['text']}")
    return "\n".join(lines)


def _slot_name_matches(token: str, slot: dict) -> bool:
    token = token.lower()
    mention = (slot.get("mention") or "").lower()
    canonical = (slot.get("canonical") or "").lower()
    return bool(
        token in mention
        or token in canonical
        or mention.startswith(token)
        or canonical.startswith(token)
    )


def _mark_slot_skipped(line_slots: list[dict], token: str) -> None:
    for slot in line_slots:
        if _slot_name_matches(token, slot):
            slot["skipped"] = True


def empty_aim_exploration() -> dict:
    return {
        "action": None,
        "selected_plan_ids": [],
        "keep_plan_ids": [],
        "change_plan_ids": [],
        "change_notes": None,
        "reject_current_plan": False,
    }


def parse_aim_exploration(clarification: dict | None) -> dict:
    if not clarification or not isinstance(clarification, dict):
        return empty_aim_exploration()
    raw = clarification.get("aim_exploration")
    if not raw or not isinstance(raw, dict):
        return empty_aim_exploration()
    result = empty_aim_exploration()
    action = raw.get("action")
    if action:
        result["action"] = str(action).strip()
    for key in ("selected_plan_ids", "keep_plan_ids", "change_plan_ids"):
        ids = raw.get(key) or []
        if isinstance(ids, list):
            result[key] = [int(i) for i in ids if str(i).isdigit()]
    notes = raw.get("change_notes")
    if notes:
        result["change_notes"] = str(notes).strip()
    result["reject_current_plan"] = bool(raw.get("reject_current_plan"))
    if result["action"] == "reject_plan":
        result["reject_current_plan"] = True
    return result


def aim_exploration_has_action(aim_exploration: dict | None) -> bool:
    return bool((aim_exploration or {}).get("action"))


def clarification_is_empty(clarification: dict | None) -> bool:
    if not clarification or not isinstance(clarification, dict):
        return True
    skip = clarification.get("skip_mentions") or []
    active = clarification.get("active_mention")
    intent = clarification.get("intent_mode")
    wants = clarification.get("wants_suggested_aims", False)
    aim_exploration = parse_aim_exploration(clarification)
    has_explore = aim_exploration_has_action(aim_exploration) or aim_exploration.get("reject_current_plan")
    has_dataset = bool(
        clarification.get("dataset_mentions")
        or clarification.get("exclude_datasets")
        or clarification.get("include_datasets")
    )
    has_session = clarification.get("session_intent") in ("meta_question", "advisory")
    has_time_intent = bool(clarification.get("time_intent"))
    has_reuse = bool(clarification.get("reuse_alias") or clarification.get("reuse_task_id"))
    return (
        not skip
        and not active
        and not intent
        and not wants
        and not has_explore
        and not has_dataset
        and not has_session
        and not has_time_intent
        and not has_reuse
    )


def apply_clarification_from_llm(
    slots: dict, clarification: dict | None
) -> tuple[dict, bool, dict]:
    """Apply LLM clarification verdict. Returns (updated_slots, wants_suggested_aims, aim_exploration)."""
    aim_exploration = parse_aim_exploration(clarification)
    slots = dict(slots)
    if clarification_is_empty(clarification):
        return slots, False, aim_exploration

    clarification = clarification or {}
    line_slots = [dict(s) for s in _line_slots(slots)]
    wants_aims = bool(clarification.get("wants_suggested_aims"))
    explore_action = aim_exploration.get("action")
    if explore_action in (
        "propose",
        "refine",
        "confirm",
        "select",
        "reject_plan",
        "save",
        "combine_saved",
        "activate",
        "list_saved",
    ):
        wants_aims = False

    for mention in clarification.get("skip_mentions") or []:
        mention = str(mention).strip()
        if not mention:
            continue
        idx = match_mention_to_existing(mention, line_slots)
        if idx is not None:
            line_slots[idx]["skipped"] = True

    active = clarification.get("active_mention")
    if active:
        active = str(active).strip()
        idx = match_mention_to_existing(active, line_slots)
        if idx is not None:
            slots["active_line_index"] = idx
            for j, other in enumerate(line_slots):
                if j != idx and other.get("status") == "not_found":
                    other["skipped"] = True

    intent_mode = clarification.get("intent_mode")
    if intent_mode:
        scope = dict(_scope(slots))
        scope["intent_mode"] = str(intent_mode).strip()
        slots["scope"] = scope

    slots["line_slots"] = line_slots
    if slots.get("active_line_index") is not None:
        slots = sync_active_line(slots)
    else:
        slots = auto_select_active_line(slots)

    active_line = (slots.get("line") or {}).get("canonical")
    slots["dataset_context"] = merge_dataset_intent_from_clarification(
        slots.get("dataset_context"),
        clarification,
        active_line,
    )
    slots = merge_time_intent_from_clarification(clarification, slots)
    if clarification.get("session_intent") == "advisory":
        wants_aims = False
        aim_exploration = empty_aim_exploration()
    return slots, wants_aims, aim_exploration


_TIER1_BROWSE_EXCLUSIONS = (
    "what aims",
    "suggested aim",
    "what can we do",
    "what can we analyze",
    "what analysis",
    "show aims",
    "aims can we",
    "aims we can",
)

_ADVISORY_FOLLOWUP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"business plan",
        r"next step",
        r"what should (we|i) (do|be) next",
        r"what('s| is) next",
        r"roadmap",
        r"recommended (next|sequence)",
    )
]


def classify_advisory_followup(user_message: str) -> bool:
    text = (user_message or "").strip()
    if not text:
        return False
    lower = text.lower()
    if any(p in lower for p in _TIER1_BROWSE_EXCLUSIONS):
        return False
    return any(p.search(text) for p in _ADVISORY_FOLLOWUP_PATTERNS)


def parse_session_intent(
    clarification: dict | None,
    user_message: str,
    slots: dict | None = None,
) -> str:
    clar = clarification or {}
    if parse_reuse_intent(clarification):
        return "fill_slots"

    line_ok = _line_is_resolved(slots)
    if clar.get("session_intent") == "advisory" and line_ok:
        return "advisory"

    if clar.get("session_intent") == "meta_question":
        return "meta_question"
    from agents.manager.context.meta_responses import classify_meta_topic

    if classify_meta_topic(user_message):
        return "meta_question"
    if line_ok and classify_advisory_followup(user_message):
        return "advisory"
    return "fill_slots"


def parse_reuse_intent(clarification: dict | None) -> str | None:
    clar = clarification or {}
    alias = clar.get("reuse_alias")
    if alias:
        return str(alias).strip()
    task_id = clar.get("reuse_task_id")
    if task_id is not None:
        return str(task_id).strip()
    return None


def apply_clarification_fallback(user_message: str, slots: dict) -> dict:
    """Regex/word-list fallback when LLM clarification is empty on follow-up turns."""
    slots = dict(slots)
    line_slots = [dict(s) for s in _line_slots(slots)]
    if not line_slots:
        return slots

    text = user_message.lower().strip()

    if re.search(r"\bleave\b|\bskip\b|\bignore\b|\bdrop\b", text):
        for slot in line_slots:
            mention = (slot.get("mention") or "").lower()
            canonical = (slot.get("canonical") or "").lower()
            if mention and mention in text:
                slot["skipped"] = True
            elif canonical and canonical in text:
                slot["skipped"] = True

    for pattern in (
        r"(?:leave|skip|ignore|drop)\s+(?:the\s+)?(\w[\w-]*)",
    ):
        for match in re.finditer(pattern, text):
            _mark_slot_skipped(line_slots, match.group(1))

    continue_match = re.search(r"continue with\s+(\w[\w-]*)", text)
    use_match = re.search(r"use\s+(\w[\w-]*)", text)
    pick_mention = None
    if continue_match:
        pick_mention = continue_match.group(1)
    elif use_match:
        pick_mention = use_match.group(1)

    if pick_mention:
        for i, slot in enumerate(line_slots):
            if _slot_name_matches(pick_mention, slot):
                slots["active_line_index"] = i
                for j, other in enumerate(line_slots):
                    if j != i and other.get("status") == "not_found":
                        other["skipped"] = True
                slots["line_slots"] = line_slots
                return sync_active_line(slots)

    if "one analysis" in text or "same analysis" in text or "both machines" in text:
        scope = dict(_scope(slots))
        scope["intent_mode"] = "joint"
        slots["scope"] = scope
    elif "different analys" in text or "per machine" in text or "separate analys" in text:
        scope = dict(_scope(slots))
        scope["intent_mode"] = "per_slot"
        slots["scope"] = scope

    resolved = _resolved_slots({"line_slots": line_slots})
    not_found = [s for s in line_slots if s.get("status") == "not_found" and not s.get("skipped")]
    if len(resolved) == 1 and not not_found and slots.get("active_line_index") is None:
        slots["active_line_index"] = resolved[0][0]

    for i, slot in enumerate(line_slots):
        if slot.get("status") != "resolved" or slot.get("skipped"):
            continue
        mention = (slot.get("mention") or "").lower()
        canonical = (slot.get("canonical") or "").lower()
        if mention and mention in text:
            slots["active_line_index"] = i
            slots["line_slots"] = line_slots
            return sync_active_line(slots)
        if canonical and canonical.lower() in text:
            slots["active_line_index"] = i
            slots["line_slots"] = line_slots
            return sync_active_line(slots)

    slots["line_slots"] = line_slots
    slots = auto_select_active_line(slots)
    return slots


def apply_clarification(
    user_message: str,
    slots: dict,
    clarification: dict | None,
) -> tuple[dict, bool, dict, bool]:
    """LLM clarification first; regex fallback when empty on follow-up turns.

    Returns (slots, wants_suggested_aims, aim_exploration, reject_plan).
    """
    is_follow_up = bool(_line_slots(slots))
    slots, wants_aims, aim_exploration = apply_clarification_from_llm(slots, clarification)
    reject_plan = bool(aim_exploration.get("reject_current_plan"))
    if is_follow_up and clarification_is_empty(clarification):
        slots = apply_clarification_fallback(user_message, slots)
        if not wants_aims and not aim_exploration_has_action(aim_exploration):
            fb_action, fb_ids = _parse_saved_plan_fallback(user_message)
            if fb_action:
                aim_exploration = {
                    **empty_aim_exploration(),
                    "action": fb_action,
                    "selected_plan_ids": fb_ids,
                }
            elif _wants_explore_aims_fallback(user_message):
                aim_exploration = {**aim_exploration, "action": "propose"}
            elif wants_suggested_aims(user_message):
                wants_aims = True
    return slots, wants_aims, aim_exploration, reject_plan


def _parse_saved_plan_fallback(user_message: str) -> tuple[str | None, list[int]]:
    text = user_message.lower().strip()
    ids = [int(x) for x in re.findall(r"\bs(\d+)\b", text)]
    batch_ids = [int(x) for x in re.findall(r"(?:keep|use) plan\s+(\d+)", text)]
    if "combine saved" in text or "combine s" in text:
        return "combine_saved", ids or batch_ids
    if "use saved" in text or text.startswith("activate s"):
        if ids or batch_ids:
            return "activate", ids or batch_ids
        return "list_saved", []
    if "show saved" in text or "list saved" in text or text == "use saved":
        return "list_saved", []
    if "keep plan" in text and batch_ids:
        return "save", batch_ids
    if re.search(r"\bkeep plan\b", text) and batch_ids:
        return "save", batch_ids
    return None, []


def parse_clarification_extras(clarification: dict | None) -> dict:
    clar = clarification or {}
    scope = clar.get("scope_selection")
    intent = clar.get("user_explore_intent")
    goal = clar.get("session_goal")
    wishes = clar.get("column_wishes") or []
    if isinstance(wishes, str):
        wishes = [wishes]
    return {
        "scope_selection": str(scope).strip() if scope else None,
        "user_explore_intent": str(intent).strip() if intent else None,
        "session_goal": str(goal).strip() if goal else None,
        "column_wishes": [str(w).strip() for w in wishes if str(w).strip()],
    }


def _wants_explore_aims_fallback(user_message: str) -> bool:
    text = user_message.lower()
    patterns = (
        "other option",
        "more options",
        "more option",
        "still more",
        "what might we see",
        "what might we able",
        "beyond those",
        "other suggested",
        "change plan",
        "keep 1",
        "keep plan",
        "tweak plan",
        "use plan",
        "deeper analysis",
        "other analysis",
        "more analysis",
        "other deeper",
    )
    return any(p in text for p in patterns)


def _line_is_resolved(slots: dict | None) -> bool:
    if not slots:
        return False
    line = slots.get("line") or {}
    if line.get("resolved"):
        return True
    return any(
        s.get("status") == "resolved" and not s.get("skipped")
        for s in slots.get("line_slots") or []
    )


def build_line_slots_from_extraction(slots: dict, extracted: dict) -> dict:
    """Merge LLM extraction into line_slots, preserving lookup_locked slots."""
    slots = dict(slots)
    line_slots = [dict(s) for s in _line_slots(slots)]

    mentions: list[str] = []
    raw_mentions = extracted.get("line_mentions")
    if isinstance(raw_mentions, list) and raw_mentions:
        mentions = [str(m).strip() for m in raw_mentions if str(m).strip()]
    elif extracted.get("line_mention"):
        mentions = [str(extracted["line_mention"]).strip()]

    scope_data = extracted.get("scope") or {}
    scope = dict(slots.get("scope") or empty_scope())
    if isinstance(scope_data, dict):
        if scope_data.get("intent_mode"):
            scope["intent_mode"] = scope_data["intent_mode"]
        if scope_data.get("joint_aim_raw"):
            joint = str(scope_data["joint_aim_raw"]).strip()
            if joint.lower() not in _SKIP_AIM_PHRASES or not scope.get("joint_aim_raw"):
                scope["joint_aim_raw"] = joint
        if scope_data.get("joint_time_raw"):
            scope["joint_time_raw"] = str(scope_data["joint_time_raw"]).strip()

    details = extracted.get("line_slots_detail") or []
    detail_by_mention: dict[str, dict] = {}
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict) and item.get("mention"):
                detail_by_mention[normalize_mention(str(item["mention"]))] = item

    processed_indices: set[int] = set()
    merged_slots: list[dict] = []

    for mention in mentions:
        idx = match_mention_to_existing(mention, line_slots)
        if idx is not None:
            if idx in processed_indices:
                # Duplicate match — update existing entry's mention to the correction
                for existing in merged_slots:
                    if existing.get("_match_idx") == idx:
                        existing["mention"] = mention
                        break
                continue
            slot = dict(line_slots[idx])
            slot["mention"] = mention
            slot["_match_idx"] = idx
            processed_indices.add(idx)
        else:
            slot = empty_line_slot(mention)
            slot["_match_idx"] = -1

        detail = detail_by_mention.get(normalize_mention(mention), {})
        if detail.get("aim_raw"):
            slot["aim_raw"] = str(detail["aim_raw"]).strip()
        if detail.get("time_raw"):
            slot["time_raw"] = str(detail["time_raw"]).strip()

        if slot.get("lookup_locked"):
            merged_slots.append(slot)
            continue

        if slot.get("skipped"):
            merged_slots.append(slot)
            continue

        if slot.get("status") != "resolved":
            slot["status"] = "pending"
            slot["resolved"] = False
            slot["canonical"] = None
            slot["source"] = None
            slot["candidates"] = []

        merged_slots.append(slot)

    for slot in merged_slots:
        slot.pop("_match_idx", None)

    for i, slot in enumerate(line_slots):
        if i in processed_indices:
            continue
        if slot.get("lookup_locked") or slot.get("skipped"):
            merged_slots.append(dict(slot))

    scope["slot_count"] = len(merged_slots)
    if len(merged_slots) <= 1:
        scope["intent_mode"] = scope.get("intent_mode") or "single"
    elif scope.get("intent_mode") == "single":
        scope["intent_mode"] = "unclear"

    slots["scope"] = scope
    slots["line_slots"] = merged_slots

    active_idx = slots.get("active_line_index")
    if active_idx is not None and active_idx < len(merged_slots):
        slots = sync_active_line(slots, active_idx)
    elif merged_slots:
        slots = auto_select_active_line(slots)
        if slots.get("active_line_index") is None:
            first = merged_slots[0]
            slots["line"] = dict(slots.get("line") or {})
            slots["line"]["mention"] = first.get("mention")
            if first.get("resolved"):
                slots["line"]["canonical"] = first.get("canonical")
                slots["line"]["resolved"] = True
                slots["line"]["source"] = first.get("source")
                slots["line"]["candidates"] = list(first.get("candidates") or [])

    return slots
