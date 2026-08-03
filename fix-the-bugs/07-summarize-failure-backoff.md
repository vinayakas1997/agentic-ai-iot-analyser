# Fix 07 — Summarize failure backoff (30s)

## Error

When `summarizeContext` failed, the catch block was silent and `summarizingTags` cleared in `finally`. The auto-summarize effect immediately re-qualified the same tag and scheduled another call. Persistent errors (500, network) could spam the backend/LLM.

## Fix

On failure, record `summaryFailUntilRef[tag] = now + 30s`. The effect skips tags still in backoff. Success clears the backoff entry. Failures also `console.warn` for visibility.

## Files touched

- `agentic-project/frontend/src/sections/ChatSection.tsx`

## Test / verification

- Code review: fail-until map checked before scheduling; set on catch; cleared on success.
- After a forced summarize failure, no re-fire for ~30 seconds for that tag.
