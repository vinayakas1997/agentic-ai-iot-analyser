"""Global application configuration — loaded once at startup."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    db_url: str = "postgresql+asyncpg://manager_agent:manager_agent_pass@localhost:5432/manager_agent_db"
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # LLM
    vllm_base_url: str = "http://192.168.1.101:8009/v1"
    manager_model: str = "atlas-35b"
    planner_model: str = "atlas-35b"
    max_tokens: int = 8192
    temperature: float = 0.1

    # Schema verification mode: mock | bus | db
    manager_schema_verify_mode: str = "mock"

    # Chat window size (number of turn-pairs sent to LLM)
    chat_window_turns: int = 6

    # LLM client settings
    llm_max_retries: int = 3
    llm_base_delay: float = 1.0
    llm_max_delay: float = 30.0
    llm_request_timeout: float = 60.0
    llm_circuit_breaker_threshold: int = 5
    llm_circuit_breaker_reset_seconds: float = 120.0

    # API / server
    api_host: str = "0.0.0.0"
    api_port: int = 7009
    cors_origins: str = "http://localhost:7008"
    worker_poll_interval_seconds: float = 1.0
    event_retention_hours: int = 24
    manager_concurrency: int = 5
    planner_concurrency: int = 2
    executor_concurrency: int = 10
    data_dir: str = "/data"
    default_user_id: str = "98765"
    debug: bool = False
    no_proxy: str = "192.168.1.101,localhost,127.0.0.1"

    # Input validation
    max_message_length: int = 10000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton settings. Called once at process start."""
    settings = Settings()
    _apply_runtime_env(settings)
    return settings


def _apply_runtime_env(settings: Settings) -> None:
    """Apply side-effect env vars once during settings initialization."""
    if settings.no_proxy:
        os.environ["NO_PROXY"] = settings.no_proxy
        os.environ["no_proxy"] = settings.no_proxy
