# Fix 2: chatQueryResults persistence to backend (HIGH)

**Status:** DONE

## Bug Description
After sending a direct chat message, the `query_result` was stored in Zustand's `chatQueryResults` state but never persisted to the backend via `updateSessionState`. On page reload, the chat turns were restored but the table/chart results were empty.

## Root Cause
`sendUserMessage()` in `sessionStore.ts` stored `chatQueryResults` in Zustand state but did not call `api.updateSessionState()` to persist them to the backend session state. The `persistTurns()` function (which does persist) was only called from `handleRunAimSql()`, not from `handleSend()`.

## Files Changed
| File | What changed |
|------|-------------|
| `frontend/src/stores/sessionStore.ts` | Added `api.updateSessionState()` call after storing `chatQueryResults` in Zustand |

## What Was Done
1. Changed the `chatQueryResults` update to read current state, merge, then `set()` and immediately persist via `api.updateSessionState(activeSessionId, { chat_query_results: updatedResults })`
2. This ensures results survive page reload since they're now stored in the backend session state

## Verification
- [x] Frontend builds without errors (`vite build` passed)
- [x] Backend container already running

## Notes
This complements the earlier fix that stored `chatQueryResults` in Zustand. The missing piece was the backend persistence call.
