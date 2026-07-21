"""Verification Context Service — schema readiness before planner handoff."""

from __future__ import annotations

from agents.manager.verify import verify_schema


async def sync_verification_context(state: dict) -> dict:
    line_context = state.get("line_context") or {}
    schema = line_context.get("schema") or {}
    if not schema:
        return {"verified": False, "errors": ["No schema loaded"], "checked": False}

    slots = state.get("slots") or {}
    canonical = (slots.get("line") or {}).get("canonical") or line_context.get("line_name") or ""
    result = await verify_schema(
        schema,
        state.get("session_id") or "",
        state.get("user_id") or "",
        canonical,
    )
    return {
        "verified": bool(result.get("verified")),
        "errors": list(result.get("errors") or []),
        "checked": True,
        "line_name": canonical,
    }


def build_verification_inventory(verification_context: dict | None) -> dict:
    ctx = verification_context or {}
    return {
        "verified": ctx.get("verified"),
        "checked": ctx.get("checked", False),
        "errors": list(ctx.get("errors") or []),
        "ready": bool(ctx.get("verified")) if ctx.get("checked") else None,
    }


def format_verification_for_prompt(inventory: dict | None) -> str:
    inv = inventory or {}
    if not inv.get("checked"):
        return "Verification: not checked yet"
    if inv.get("verified"):
        return "Verification: schema OK"
    errs = inv.get("errors") or []
    return "Verification: failed — " + "; ".join(errs[:3])
