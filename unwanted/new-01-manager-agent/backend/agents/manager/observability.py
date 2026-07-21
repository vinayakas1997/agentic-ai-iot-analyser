"""Structured observability: logging, timing, metrics."""

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable


@dataclass
class NodeMetrics:
    calls: int = 0
    total_seconds: float = 0.0
    errors: int = 0

    @property
    def avg_seconds(self) -> float:
        return self.total_seconds / self.calls if self.calls else 0.0


_metrics: dict[str, NodeMetrics] = defaultdict(NodeMetrics)


def get_metrics() -> dict:
    return {
        name: {"calls": m.calls, "avg_ms": round(m.avg_seconds * 1000, 1), "errors": m.errors}
        for name, m in sorted(_metrics.items())
    }


def reset_metrics() -> None:
    _metrics.clear()


def timed_node(name: str) -> Callable:
    """Decorator to time and count LangGraph node executions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                _metrics[name].errors += 1
                raise
            finally:
                elapsed = time.monotonic() - t0
                _metrics[name].calls += 1
                _metrics[name].total_seconds += elapsed
        return async_wrapper
    return decorator


def log_node_error(node: str, error: Any, context: dict | None = None) -> None:
    _metrics[node].errors += 1
    logger = logging.getLogger(f"node.{node}")
    extra = {"node": node, "error": str(error)[:500]}
    if context:
        extra["context"] = {k: v for k, v in context.items() if isinstance(v, (str, int, float, bool))}
    logger.error("Node %s failed: %s", node, str(error)[:200], extra=extra)


@contextmanager
def time_operation(name: str):
    """Context manager timer for any operation."""
    t0 = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - t0
        _metrics[name].calls += 1
        _metrics[name].total_seconds += elapsed
