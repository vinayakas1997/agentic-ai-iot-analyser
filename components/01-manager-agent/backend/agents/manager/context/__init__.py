"""Manager context services — registry, time, scope, plan, session inventory."""

from agents.manager.context.session_inventory import (
    build_session_inventory,
    format_session_inventory_for_prompt,
)

__all__ = [
    "build_session_inventory",
    "format_session_inventory_for_prompt",
]
