from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from config import get_settings as get_edas_settings


class ManagerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    manager_model: str = "atlas-35b"
    manager_schema_verify_mode: str = "mock"  # mock | bus (bus = Phase 2)


@lru_cache
def get_manager_settings() -> ManagerSettings:
    return ManagerSettings()


def get_llm_config() -> dict:
    edas = get_edas_settings()
    mgr = get_manager_settings()
    return {
        "base_url": edas.vllm_base_url,
        "model": mgr.manager_model,
        "temperature": edas.temperature,
        "max_tokens": edas.max_tokens,
    }


def get_chat_window_turns() -> int:
    return 6
