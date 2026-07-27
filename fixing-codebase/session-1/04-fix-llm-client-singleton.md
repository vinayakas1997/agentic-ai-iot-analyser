# Fix 4: Singleton LLM client (MEDIUM)

**Status:** DONE

## Bug Description
Every LLM call created a new `AsyncOpenAI` client instance — 8 instantiation sites across `llm_client.py` (4 sites) and `aims.py` (4 sites). This means TCP connection setup/teardown on every LLM call, adding latency to each request. In the DEEP route's multi-iteration loop, up to 6+ new clients could be created per request.

## Root Cause
All LLM functions independently created `AsyncOpenAI(base_url=..., api_key="EMPTY", timeout=...)` instead of reusing a shared client.

## Files Changed
| File | What changed |
|------|-------------|
| `backend/config.py` | Added `get_llm_client()` function with module-level singleton and `AsyncOpenAI` import |
| `backend/llm_client.py` | Removed `from openai import AsyncOpenAI`, replaced all 4 client instantiations with `get_llm_client()` |
| `backend/aims.py` | Removed `from openai import AsyncOpenAI`, replaced all 4 client instantiations with `get_llm_client()` |

## What Was Done
1. Added `AsyncOpenAI` import and `get_llm_client()` function to `config.py` — creates the client once on first call, reuses it thereafter
2. Updated all 8 call sites across `llm_client.py` and `aims.py` to use `get_llm_client()` instead of `AsyncOpenAI(...)`

## Verification
- [x] All 3 files parse successfully
- [x] No remaining `AsyncOpenAI(` calls outside `config.py`
- [x] Backend container rebuilt and restarted successfully

## Notes
The API key is still hardcoded as "EMPTY" in the singleton (works with vLLM). This should be made configurable if switching to a real OpenAI API.
