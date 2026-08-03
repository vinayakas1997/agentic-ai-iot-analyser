# Fix 01 — Message save retries without re-running the LLM

## Error

`POST /api/v2/messages` ran the full LLM pipeline first, then saved the turn with optimistic locking (`version`). If a concurrent PATCH bumped/conflicted the version, the API returned **409**. The frontend `withRetry` then **replayed the entire request**, including classify / FOCUS / extract-actions LLM calls. Same class of bug as the summarize infinite loop.

## Fix

Added `_commit_session_state()` in `backend/api.py`. After LLM work finishes, the turn is applied and committed with up to 5 version-conflict retries. Each retry re-reads fresh state and re-applies the mutation — **no second LLM call**.

Applied to both SUMMARY-mode and RESEARCH-mode save paths in `send_message`.

## Files touched

- `agentic-project/backend/api.py`

## Test / verification

- Static review: both previous `select(... version == expected_version)` save blocks replaced by `_commit_session_state`.
- Unused `expected_version` capture at start of `send_message` removed (save no longer depends on stale start-of-request version).
- Rebuild backend container after deploy; send a chat message and confirm a single response with no repeated `chat/completions` storm on concurrent UI persists.
