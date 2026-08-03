# Fix 05 — Include userId in triggerSummary dependencies

## Error

`triggerSummary` used `userId` but `useCallback` deps were only `[sessionId]`. If auth/`userId` loaded after mount, summarize calls could send a stale/missing `userId` and get 403.

## Fix

Deps updated to `[sessionId, userId]`.

## Files touched

- `agentic-project/frontend/src/sections/ChatSection.tsx`

## Test / verification

- Code review: `useCallback(..., [sessionId, userId])`.
