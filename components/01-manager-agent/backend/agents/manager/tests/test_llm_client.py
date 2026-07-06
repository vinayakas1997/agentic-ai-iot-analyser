"""Tests for the LLM client with retry and circuit breaker."""

import pytest

from agents.manager.llm_client import LLMClient, get_llm_stats


class TestLLMClientInit:
    def test_default_config(self):
        client = LLMClient()
        assert client.max_retries == 3
        assert client.base_delay == 1.0
        assert client.circuit_breaker_threshold == 5

    def test_custom_config(self):
        client = LLMClient(max_retries=5, base_delay=2.0, circuit_breaker_threshold=3)
        assert client.max_retries == 5
        assert client.base_delay == 2.0
        assert client.circuit_breaker_threshold == 3

    def test_consecutive_failures_zero_on_init(self):
        client = LLMClient()
        assert client._consecutive_failures == 0

    def test_circuit_open_until_zero_on_init(self):
        client = LLMClient()
        assert client._circuit_open_until == 0.0


class TestLLMClientCircuitBreaker:
    def test_record_failure_opens_circuit_at_threshold(self, monkeypatch):
        client = LLMClient(circuit_breaker_threshold=3, circuit_breaker_reset_seconds=60)
        import time as time_module
        fake_time = [100.0]
        monkeypatch.setattr(time_module, "monotonic", lambda: fake_time[0])

        for i in range(3):
            client._consecutive_failures = i
            client._record_failure()

        assert client._consecutive_failures >= 3
        assert client._circuit_open_until > 0

    def test_record_success_resets_failures(self):
        client = LLMClient()
        client._consecutive_failures = 3
        client._record_success()
        assert client._consecutive_failures == 0
        assert client._circuit_open_until == 0.0


class TestLLMClientStats:
    def test_stats_initial_state(self):
        stats = get_llm_stats()
        assert "total_calls" in stats
        assert "errors" in stats


class TestLLMClientGetSet:
    def test_get_llm_returns_client(self):
        from agents.manager.llm_client import get_llm
        client = get_llm()
        assert client is not None

    def test_set_llm_for_test_replaces_client(self):
        from agents.manager.llm_client import get_llm, set_llm_for_test
        original = get_llm()
        new_client = LLMClient(max_retries=1)
        set_llm_for_test(new_client)
        assert get_llm() is new_client
        # Restore
        set_llm_for_test(None)
        assert get_llm() is not new_client
