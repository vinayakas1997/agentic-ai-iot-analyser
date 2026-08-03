import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AsyncOpenAI

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = "postgresql+asyncpg://manager_agent:manager_agent_pass@localhost:5432/manager_agent_db"

    vllm_base_url: str = "http://172.21.0.1:8009/v1"
    llm_model: str = "qwen36-35B"
    max_tokens: int = 4096
    temperature: float = 0.1

    llm_max_retries: int = 3
    llm_request_timeout: float = 120.0

    # Agentic tool-call round budgets. When a run exhausts its budget it is forced to
    # answer from the data gathered so far and the response is flagged `truncated`.
    focus_max_rounds: int = 12
    template_max_rounds: int = 16

    # Overall token budget for the composed system prompt (context + enrichment +
    # previously-fetched + conversation history + aim descriptions). When exceeded,
    # components are truncated by priority: oldest conversation turns first, then
    # oldest previously-fetched entries, then oldest enrichment summaries.
    prompt_max_tokens: int = 6000

    api_host: str = "0.0.0.0"
    api_port: int = 7010
    cors_origins: str = "http://localhost:7008,http://127.0.0.1:7008,http://localhost:7010"
    debug: bool = False
    log_level: int = 0

    max_upload_size_mb: int = 50
    user_data_dir: str = "/data/users"
    max_bad_row_pct: float = 5.0

    # Path to the IoT user allowlist JSON file.
    # Edit this file at runtime to add/remove IoT users without restarting.
    iot_user_ids_path: str = "/app/iot_users.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def get_iot_user_ids(self) -> set[str]:
        """Read IoT user IDs from the JSON file on every call — no restart needed."""
        try:
            raw = Path(self.iot_user_ids_path).read_text(encoding="utf-8")
            ids: list[str] = json.loads(raw)
            return {u.strip().lower() for u in ids if isinstance(u, str) and u.strip()}
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            return set()

@lru_cache
def get_settings() -> Settings:
    return Settings()

_llm_client: AsyncOpenAI | None = None

def get_llm_client() -> AsyncOpenAI:
    """Get or create a shared AsyncOpenAI client singleton."""
    global _llm_client
    if _llm_client is None:
        settings = get_settings()
        _llm_client = AsyncOpenAI(
            base_url=settings.vllm_base_url,
            api_key="EMPTY",
            timeout=settings.llm_request_timeout,
        )
    return _llm_client
