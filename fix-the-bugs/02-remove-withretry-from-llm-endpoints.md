# Fix 02 — Stop frontend withRetry from replaying LLM endpoints

## Error

`withRetry()` in `frontend/src/api/client.ts` retried any **409** up to 3 times for:
- `sendMessage` (`/messages`)
- `executeQuery` (`/execute-query`)
- `summarizeContext` (`/summarize-context`)

Those endpoints do expensive LLM work. A conflict after the LLM finished caused a full client-side replay (more LLM calls). This amplified the summarize spam we saw earlier.

## Fix

Removed `withRetry` from those three LLM endpoints. They now call `request()` once.

Kept `withRetry` on `updateSessionState` (PATCH) — that path has no LLM and benefits from conflict retry.

Backend already retries summarize save, and message save now retries via `_commit_session_state` (Fix 01).

## Files touched

- `agentic-project/frontend/src/api/client.ts`

## Test / verification

- Grep: `withRetry` remains only for session PATCH + helper definition.
- After rebuild, concurrent persist + chat should not triple LLM traffic on 409.
