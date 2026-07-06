from openai import AsyncOpenAI

from config import get_settings

settings = get_settings()
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=settings.vllm_base_url, api_key="not-needed")
    return _client


async def complete(model: str, messages: list[dict[str, str]]) -> str:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )
    return response.choices[0].message.content or ""
