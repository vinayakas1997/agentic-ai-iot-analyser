"""Per-session trace recorder for the manager graph.

Records every debug event, routing decision, LLM call, and state snapshot
unconditionally (no config gate). Exposed via GET /manager/trace/<session_id>.
"""

import contextvars
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

EventType = Literal[
    "debug",
    "node_state",
    "routing",
    "llm_input",
    "llm_output",
    "llm_meta",
]


@dataclass
class TraceEvent:
    turn: int = 0
    node: str = ""
    event_type: EventType = "debug"
    timestamp: str = ""
    data: dict[str, Any] = field(default_factory=dict)


_traces: dict[str, list[TraceEvent]] = {}
_turn_counters: dict[str, int] = {}
_current_session: contextvars.ContextVar[str] = contextvars.ContextVar("tracer_session_id", default="")


def set_session(session_id: str) -> None:
    _current_session.set(session_id)
    if session_id not in _turn_counters:
        _turn_counters[session_id] = 0


def get_session() -> str:
    return _current_session.get()


def clear_session() -> None:
    _current_session.set("")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _turn(session_id: str) -> int:
    return _turn_counters.get(session_id, 0)


def bump_turn(session_id: str) -> int:
    _turn_counters[session_id] = _turn_counters.get(session_id, 0) + 1
    return _turn_counters[session_id]


def record(
    event_type: EventType,
    node: str = "",
    **data: Any,
) -> None:
    session_id = _current_session.get()
    if not session_id:
        return
    if session_id not in _traces:
        _traces[session_id] = []
    _traces[session_id].append(
        TraceEvent(
            turn=_turn(session_id),
            node=node,
            event_type=event_type,
            timestamp=_ts(),
            data=data,
        )
    )


def get_trace(session_id: str) -> list[dict[str, Any]]:
    events = _traces.get(session_id, [])
    return [
        {
            "turn": e.turn,
            "node": e.node,
            "event_type": e.event_type,
            "timestamp": e.timestamp,
            "data": e.data,
        }
        for e in events
    ]


def clear_trace(session_id: str) -> None:
    _traces.pop(session_id, None)
    _turn_counters.pop(session_id, None)
