import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_runtime_env_applied = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = "postgresql+asyncpg://edas:edas@192.168.1.101:9001/edas"
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    vllm_base_url: str = "http://192.168.1.101:8009/v1"
    manager_model: str = "atlas-35b"
    research_model: str = "atlas-35b"
    max_tokens: int = 2048
    temperature: float = 0.1
    api_host: str = "0.0.0.0"
    api_port: int = 7009
    cors_origins: str = "http://localhost:7008"
    worker_poll_interval_seconds: float = 1.0
    event_retention_hours: int = 24
    manager_concurrency: int = 5
    research_concurrency: int = 2
    executor_concurrency: int = 10
    data_dir: str = "/data"
    default_user_id: str = "98765"
    debug: bool = False
    no_proxy: str = "192.168.1.101,localhost,127.0.0.1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def apply_runtime_env() -> None:
    """Apply side-effect env vars (NO_PROXY) once per process."""
    global _runtime_env_applied
    if _runtime_env_applied:
        return
    settings = get_settings()
    if settings.no_proxy:
        os.environ["NO_PROXY"] = settings.no_proxy
        os.environ["no_proxy"] = settings.no_proxy
    _runtime_env_applied = True
