from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PlannerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = "postgresql+asyncpg://manager_agent:manager_agent_pass@localhost:5432/manager_agent_db"
    vllm_base_url: str = "http://192.168.1.101:8009/v1"
    planner_model: str = "atlas-35b"
    max_tokens: int = 2048
    temperature: float = 0.1
    planner_concurrency: int = 2
    max_retries: int = 3
    max_queries_per_task: int = 4


@lru_cache
def get_settings() -> PlannerSettings:
    return PlannerSettings()
