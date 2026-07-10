"""Manager agent configuration — delegates to global Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from config import get_settings as get_edas_settings


class ManagerSettings(BaseSettings):
    """Override-able manager-specific settings via env file."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    manager_model: str | None = None
    manager_schema_verify_mode: str | None = None
    chat_window_turns: int | None = None


@lru_cache
def get_manager_settings() -> ManagerSettings:
    return ManagerSettings()


def get_llm_config() -> dict:
    edas = get_edas_settings()
    mgr = get_manager_settings()
    return {
        "base_url": edas.vllm_base_url,
        "model": mgr.manager_model or edas.manager_model,
        "temperature": edas.temperature,
        "max_tokens": edas.max_tokens,
        "max_retries": edas.llm_max_retries,
        "base_delay": edas.llm_base_delay,
        "max_delay": edas.llm_max_delay,
        "request_timeout": edas.llm_request_timeout,
        "circuit_breaker_threshold": edas.llm_circuit_breaker_threshold,
        "circuit_breaker_reset_seconds": edas.llm_circuit_breaker_reset_seconds,
    }


def get_schema_verify_mode() -> str:
    edas = get_edas_settings()
    mgr = get_manager_settings()
    return mgr.manager_schema_verify_mode or edas.manager_schema_verify_mode


def get_chat_window_turns() -> int:
    edas = get_edas_settings()
    mgr = get_manager_settings()
    return mgr.chat_window_turns or edas.chat_window_turns
