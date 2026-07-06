"""Shared LLM client with retry, timeout, circuit-breaker, and observability."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from agents.manager.config import get_llm_config
from agents.manager.debug_log import log_llm_call

logger = logging.getLogger(__name__)


@dataclass
class LLMCallStats:
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    total_calls: int = 0
    token_estimates: list[int] = field(default_factory=list)

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    @property
    def error_rate(self) -> float:
        return self.errors / self.total_calls if self.total_calls else 0.0


_stats = LLMCallStats()


def get_llm_stats() -> dict:
    return {
        "total_calls": _stats.total_calls,
        "errors": _stats.errors,
        "avg_latency_ms": round(_stats.avg_latency * 1000, 1),
        "error_rate_pct": round(_stats.error_rate * 100, 1),
    }


class LLMClient:
    """Thread-safe LLM client with retry and circuit breaker."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        request_timeout: float = 60.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_reset_seconds: float = 120.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.request_timeout = request_timeout
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_reset_seconds = circuit_breaker_reset_seconds

        self._client: ChatOpenAI | None = None
        self._consecutive_failures = 0
        self._circuit_open_until: float = 0.0
        self._lock = asyncio.Lock()

    def _create_client(self) -> ChatOpenAI:
        cfg = get_llm_config()
        return ChatOpenAI(
            base_url=cfg["base_url"],
            api_key="not-needed",
            model=cfg["model"],
            temperature=cfg["temperature"],
            max_tokens=cfg["max_tokens"],
            timeout=self.request_timeout,
        )

    @property
    def client(self) -> ChatOpenAI:
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def reset_client(self) -> None:
        self._client = self._create_client()

    async def _check_circuit_breaker(self) -> None:
        if self._circuit_open_until > time.monotonic():
            remaining = round(self._circuit_open_until - time.monotonic(), 1)
            raise RuntimeError(
                f"Circuit breaker open — LLM unavailable for {remaining}s "
                f"({self._consecutive_failures} consecutive failures)"
            )

    async def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    async def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.circuit_breaker_threshold:
            self._circuit_open_until = time.monotonic() + self.circuit_breaker_reset_seconds
            logger.warning(
                "LLM circuit breaker opened after %d failures (reset in %ss)",
                self._consecutive_failures,
                self.circuit_breaker_reset_seconds,
            )

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        *,
        caller: str = "unknown",
        retry_count: int | None = None,
    ) -> Any:
        max_attempts = (retry_count if retry_count is not None else self.max_retries) + 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            async with self._lock:
                await self._check_circuit_breaker()

            try:
                t0 = time.monotonic()
                response = await self.client.ainvoke(messages)
                latency = time.monotonic() - t0

                async with self._lock:
                    await self._record_success()
                    _stats.total_calls += 1
                    _stats.latencies.append(latency)

                content_len = len(str(getattr(response, "content", "")))
                log_llm_call(caller, latency * 1000, tokens=content_len // 4, success=True)
                logger.debug(
                    "LLM call %s attempt %d/%d OK (%.1fs, ~%d chars)",
                    caller, attempt, max_attempts, latency, content_len,
                )
                return response

            except Exception as e:
                last_error = e
                latency = time.monotonic() - t0 if 't0' in dir() else 0.0

                async with self._lock:
                    _stats.errors += 1
                    _stats.total_calls += 1
                    await self._record_failure()

                log_llm_call(caller, latency * 1000, success=False)
                logger.warning(
                    "LLM call %s attempt %d/%d failed after %.1fs: %s: %s",
                    caller, attempt, max_attempts, latency,
                    type(e).__name__, str(e)[:200],
                )

                if attempt < max_attempts:
                    delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                    logger.info("Retrying %s in %.1fs (attempt %d/%d)", caller, delay, attempt + 1, max_attempts)
                    await asyncio.sleep(delay)
                    self.reset_client()

        raise RuntimeError(
            f"LLM call {caller} failed after {max_attempts} attempts. "
            f"Last error: {type(last_error).__name__}: {last_error}"
        ) from last_error


_client = LLMClient()


def get_llm() -> LLMClient:
    return _client


def set_llm_for_test(client: LLMClient | None) -> None:
    global _client
    if client is None:
        _client = LLMClient()
    else:
        _client = client
