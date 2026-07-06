"""Template-first answers for session meta questions."""

from __future__ import annotations

import re

_META_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"what tables|which tables|tables loaded|datasets loaded|what('s| is) loaded", re.I), "tables_loaded"),
    (re.compile(r"what('s| is) (still )?missing|what do you (still )?need", re.I), "missing"),
    (re.compile(r"is time required|do i need (a )?time|time optional|need a date", re.I), "time_required"),
    (re.compile(r"what time|time range|date filter|which dates", re.I), "time_status"),
    (re.compile(r"which line|active line|what line|both machines|comparing both", re.I), "scope"),
    (re.compile(r"what (were |are )?(the )?(3 |three )?options|proposals|plans (did )?we (pick|choose)", re.I), "proposals"),
    (re.compile(r"what plan|picked plan|confirmed plan|current plan", re.I), "plan"),
    (re.compile(r"can i join|join .+ and|how to join", re.I), "joins"),
    (re.compile(r"is (the )?data ready|schema ready|verification|verify", re.I), "verification"),
    (re.compile(r"last (run|task|analysis)|previous task|task history|same as last", re.I), "task_history"),
]


def classify_meta_topic(user_message: str) -> str | None:
    text = (user_message or "").strip()
    if not text:
        return None
    for pattern, topic in _META_PATTERNS:
        if pattern.search(text):
            return topic
    return None


def answer_session_meta(user_message: str, inventory: dict) -> str:
    topic = classify_meta_topic(user_message) or "overview"
    handlers = {
        "tables_loaded": _answer_tables_loaded,
        "missing": _answer_missing,
        "time_required": _answer_time_required,
        "time_status": _answer_time_status,
        "scope": _answer_scope,
        "proposals": _answer_proposals,
        "plan": _answer_plan,
        "joins": _answer_joins,
        "verification": _answer_verification,
        "task_history": _answer_task_history,
        "overview": _answer_overview,
    }
    handler = handlers.get(topic, _answer_overview)
    return handler(inventory)


def _answer_tables_loaded(inv: dict) -> str:
    registry = inv.get("registry") or {}
    lines = registry.get("lines") or []
    if not lines:
        return "No line context is loaded yet. Tell me which machine or line to analyze."
    parts = ["**Loaded tables by line:**"]
    for line_info in lines:
        name = line_info.get("line_name")
        avail = line_info.get("available_datasets") or []
        inc = line_info.get("included_datasets") or avail
        exc = line_info.get("excluded_datasets") or []
        parts.append(f"- **{name}**: available {', '.join(avail) or 'none'}")
        parts.append(f"  In scope: {', '.join(inc) or 'all'}")
        if exc:
            parts.append(f"  Excluded: {', '.join(exc)}")
    return "\n".join(parts)


def _answer_missing(inv: dict) -> str:
    missing = inv.get("missing") or []
    if not missing:
        return "Nothing required is missing right now — we can proceed or refine the plan."
    labels = {"line": "production line / machine", "aim": "analysis aim", "time": "time range (optional)"}
    items = [labels.get(m, m) for m in missing]
    return "**Still needed:** " + ", ".join(items)


def _answer_time_required(inv: dict) -> str:
    time_inv = inv.get("time") or {}
    if time_inv.get("required_for_plan"):
        return "Yes — a time range is required for this task."
    return (
        "Time is **optional**. If you skip it, we use all available data. "
        "You can say e.g. *last week* or *no date filter*."
    )


def _answer_time_status(inv: dict) -> str:
    time_inv = inv.get("time") or {}
    status = time_inv.get("status") or "not_specified"
    if status == "not_specified":
        return "No time filter set yet (optional)."
    if status == "all_data":
        return "Using **all available data** — no date filter."
    if status == "resolved":
        return f"Time range: **{time_inv.get('start')}** → **{time_inv.get('end')}**"
    if status == "ambiguous":
        return f"Time phrase **{time_inv.get('raw')}** is ambiguous — please clarify."
    return f"Time status: {status} ({time_inv.get('raw') or 'n/a'})"


def _answer_scope(inv: dict) -> str:
    scope = inv.get("scope") or {}
    mode = scope.get("intent_mode") or "single"
    active = scope.get("active_line")
    lines = []
    lines.append(f"Scope mode: **{mode}**")
    if active:
        lines.append(f"Active line: **{active}**")
    for e in scope.get("line_entries") or []:
        if e.get("skipped"):
            continue
        label = e.get("canonical") or e.get("mention") or "?"
        lines.append(f"- {e.get('mention')} → {label} ({e.get('status')})")
    return "\n".join(lines) if lines else "No multi-line scope configured yet."


def _answer_proposals(inv: dict) -> str:
    plan = inv.get("plan_explore") or {}
    proposals = plan.get("proposals") or []
    if not proposals:
        return "No analysis proposals on the table yet. Ask for suggested aims or say *show me other options*."
    lines = ["**Current proposals:**"]
    for p in proposals:
        lines.append(f"{p.get('id')}. **{p.get('title')}**")
        ds = p.get("datasets_used") or []
        if ds:
            lines.append(f"   Datasets: {', '.join(ds)}")
    return "\n".join(lines)


def _answer_plan(inv: dict) -> str:
    plan = inv.get("plan_explore") or {}
    aims = plan.get("plan_aims") or []
    if not aims:
        return "No confirmed plan yet — we're still collecting aims or exploring options."
    lines = ["**Confirmed plan aims:**"]
    for a in aims:
        lines.append(f"- {a}")
    if plan.get("plan_line"):
        lines.insert(0, f"Line: **{plan['plan_line']}**")
    return "\n".join(lines)


def _answer_joins(inv: dict) -> str:
    join = inv.get("join") or {}
    known = join.get("known_joins") or []
    suggested = join.get("suggested_joins") or []
    if not known and not suggested:
        return "No join information loaded yet — resolve a line with multiple datasets first."
    parts = []
    if known:
        parts.append("**Known joins:**")
        for e in known:
            on = ", ".join(e.get("on") or [])
            parts.append(f"- {e.get('from_dataset')}.{on} → {e.get('to_dataset')}.{on}")
    if suggested:
        parts.append("\n**Suggested joins** (verify column meaning before use):")
        for e in suggested[:5]:
            on = ", ".join(e.get("on") or [])
            parts.append(f"- {e.get('from_dataset')}.{on} → {e.get('to_dataset')}.{on}")
    return "\n".join(parts)


def _answer_verification(inv: dict) -> str:
    verify = inv.get("verification") or {}
    if not verify.get("checked"):
        return "Schema verification has not run yet — it runs when you confirm the plan."
    if verify.get("verified"):
        return "Data schema looks **ready** for planner handoff."
    errs = verify.get("errors") or []
    return "**Schema not ready:** " + "; ".join(errs[:5])


def _answer_task_history(inv: dict) -> str:
    hist = inv.get("task_history") or {}
    if not hist.get("count"):
        return "No saved tasks for this line yet."
    lines = [f"**{hist['count']}** saved task(s) for this line."]
    if hist.get("latest_alias"):
        lines.append(f"Latest: **{hist['latest_alias']}** (v{hist.get('latest_version')})")
    for e in hist.get("entries") or []:
        aims = "; ".join(e.get("aims") or [])[:80]
        alias = e.get("alias_name") or f"v{e.get('version')}"
        lines.append(f"- {alias}: {aims or '(no aims recorded)'}")
    return "\n".join(lines)


def _answer_overview(inv: dict) -> str:
    parts = [
        _answer_missing(inv),
        _answer_tables_loaded(inv) if (inv.get("registry") or {}).get("lines") else "",
        _answer_time_status(inv),
    ]
    return "\n\n".join(p for p in parts if p)
