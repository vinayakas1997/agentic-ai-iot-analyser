"""Task History Context Service — prior saved task definitions."""

from __future__ import annotations
import logging

from agents.manager.db import fetch_task_versions

logger = logging.getLogger(__name__)


async def fetch_task_history(user_id: str, line_name: str, *, limit: int = 5) -> list[dict]:
    if not user_id or not line_name:
        return []
    try:
        rows = await fetch_task_versions(user_id, line_name)
    except Exception:
        logger.exception("fetch_task_history: DB fetch failed for user=%s line=%s", user_id, line_name)
        return []
    history: list[dict] = []
    for row in rows[:limit]:
        td = row.get("task_definition") or {}
        history.append(
            {
                "version": row.get("version"),
                "line_name": row.get("line_name"),
                "alias_name": td.get("alias_name"),
                "aims": td.get("aims") or [],
                "time_range": td.get("time_range"),
                "datasets_in_scope": td.get("datasets_in_scope") or [],
            }
        )
    return history


def resolve_task_alias(mention: str, history: list[dict]) -> dict | None:
    raw = (mention or "").strip().lower()
    if not raw or not history:
        return None
    for entry in history:
        alias = (entry.get("alias_name") or "").strip().lower()
        if alias and (raw == alias or raw in alias or alias in raw):
            return entry
    if raw in ("last", "previous", "last run", "same as before") and history:
        return history[0]
    return None


def build_task_history_inventory(state: dict, history: list[dict] | None = None) -> dict:
    hist = history or []
    latest = hist[0] if hist else None
    return {
        "count": len(hist),
        "latest_version": latest.get("version") if latest else None,
        "latest_alias": latest.get("alias_name") if latest else None,
        "entries": [
            {"version": h.get("version"), "alias_name": h.get("alias_name"), "aims": h.get("aims") or []}
            for h in hist[:3]
        ],
    }


def format_task_history_for_prompt(inventory: dict | None) -> str:
    inv = inventory or {}
    if not inv.get("count"):
        return "Task history: none for this line"
    lines = [f"Task history: {inv.get('count')} saved version(s)"]
    if inv.get("latest_alias"):
        lines.append(f"Latest alias: **{inv['latest_alias']}** (v{inv.get('latest_version')})")
    return "\n".join(lines)


async def load_task_history_for_state(state: dict) -> list[dict]:
    slots = state.get("slots") or {}
    canonical = (slots.get("line") or {}).get("canonical") or ""
    user_id = state.get("user_id") or ""
    return await fetch_task_history(user_id, canonical)
