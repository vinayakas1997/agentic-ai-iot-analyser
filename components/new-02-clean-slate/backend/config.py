import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = "postgresql+asyncpg://manager_agent:manager_agent_pass@localhost:5432/manager_agent_db"

    vllm_base_url: str = "http://172.21.0.1:8009/v1"
    llm_model: str = "qwen36-35B"
    max_tokens: int = 4096
    temperature: float = 0.1

    llm_max_retries: int = 3
    llm_request_timeout: float = 120.0

    api_host: str = "0.0.0.0"
    api_port: int = 7010
    cors_origins: str = "http://localhost:7008"
    default_user_id: str = "98765"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
