# Fix 06 — Top-level sqlalchemy `select` import

## Error

`select` was imported locally inside many handlers. `summarize_context` previously missed the local import and crashed with `NameError: name 'select' is not defined`, which (with frontend retries) caused hundreds of wasted LLM calls.

## Fix

Added `from sqlalchemy import select` at module top of `api.py`. Helper `_get_session_owned` / `_commit_session_state` use the top-level import. Reduces chance of another missed local import.

## Files touched

- `agentic-project/backend/api.py`

## Test / verification

- Import present at top of `api.py`.
- `_commit_session_state` and `_get_session_owned` no longer need local imports.
- (Some other handlers may still have redundant local imports; harmless.)
