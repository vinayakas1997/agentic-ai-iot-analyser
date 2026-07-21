from datetime import datetime, timezone

from agents.manager.state import ManagerState


def inject_reference_time(state: ManagerState) -> ManagerState:
    now = datetime.now(timezone.utc)
    return {
        **state,
        "reference_now": now.isoformat(),
        "reference_timezone": state.get("reference_timezone") or "UTC",
    }
