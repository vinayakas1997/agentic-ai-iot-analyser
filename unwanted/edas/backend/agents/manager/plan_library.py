"""Session saved-plan shortlist (max 5) and combine helpers."""

from __future__ import annotations

MAX_SAVED_PLANS = 5


def _coerce_aims(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    return []


def next_saved_id(saved_plans: list[dict]) -> str:
    used = {p.get("id") for p in saved_plans if isinstance(p, dict)}
    for i in range(1, MAX_SAVED_PLANS + 1):
        sid = f"S{i}"
        if sid not in used:
            return sid
    return f"S{len(saved_plans) + 1}"


def proposal_to_saved_card(proposal: dict, *, source: str = "explore_batch") -> dict:
    return {
        "id": proposal.get("saved_id") or "",
        "title": proposal.get("title") or "Saved plan",
        "aims": _coerce_aims(proposal.get("aims")),
        "benefits": proposal.get("benefits") or "",
        "datasets_used": list(proposal.get("datasets_used") or []),
        "columns_used": list(proposal.get("columns_used") or []),
        "lines_used": list(proposal.get("lines_used") or []),
        "what_you_might_see": proposal.get("what_you_might_see") or "",
        "join_description": proposal.get("join_description") or "",
        "source": source,
    }


def append_saved_plan(saved_plans: list[dict], card: dict) -> tuple[list[dict], str | None]:
    plans = [dict(p) for p in saved_plans if isinstance(p, dict)]
    if len(plans) >= MAX_SAVED_PLANS:
        return plans, (
            f"You already have {MAX_SAVED_PLANS} saved plans. "
            "Combine or drop one before saving another."
        )
    sid = next_saved_id(plans)
    entry = dict(card)
    entry["id"] = sid
    plans.append(entry)
    return plans, None


def find_saved(saved_plans: list[dict], ref: str | int) -> dict | None:
    text = str(ref).strip().upper()
    if text.startswith("S"):
        key = text
    elif text.isdigit():
        key = f"S{text}"
    else:
        key = text
    for p in saved_plans or []:
        if not isinstance(p, dict):
            continue
        if str(p.get("id", "")).upper() == key:
            return p
    return None


def combine_saved_cards(cards: list[dict]) -> dict:
    aims: list[str] = []
    titles: list[str] = []
    datasets: list[str] = []
    columns: list[str] = []
    lines: list[str] = []
    benefits_parts: list[str] = []
    see_parts: list[str] = []
    for card in cards:
        for a in card.get("aims") or []:
            if a not in aims:
                aims.append(a)
        if card.get("title"):
            titles.append(str(card["title"]))
        for d in card.get("datasets_used") or []:
            if d not in datasets:
                datasets.append(d)
        for c in card.get("columns_used") or []:
            if c not in columns:
                columns.append(c)
        for ln in card.get("lines_used") or []:
            if ln not in lines:
                lines.append(ln)
        if card.get("benefits"):
            benefits_parts.append(str(card["benefits"]))
        if card.get("what_you_might_see"):
            see_parts.append(str(card["what_you_might_see"]))
    return {
        "title": " + ".join(titles) if titles else "Combined plan",
        "aims": aims,
        "benefits": "\n".join(benefits_parts),
        "datasets_used": datasets,
        "columns_used": columns,
        "lines_used": lines,
        "what_you_might_see": " ".join(see_parts),
        "source": "combined_saved",
    }


def format_saved_list(saved_plans: list[dict]) -> str:
    if not saved_plans:
        return "No saved plans yet. Say **keep plan 2** after a batch to save one."
    lines = ["**Saved plans:**", ""]
    for p in saved_plans:
        aims = p.get("aims") or []
        aim_text = "; ".join(aims) if aims else "(no aims)"
        lines.append(f"- **{p.get('id')}** — {p.get('title', 'Plan')}: {aim_text}")
    lines.append("")
    lines.append("Say **use saved S1** to activate, or **combine saved S1 and S2**.")
    return "\n".join(lines)
