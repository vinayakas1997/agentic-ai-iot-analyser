# Fix 3: reopenSession/forkSession dead code (MEDIUM)

**Status:** DONE

## Bug Description
`reopenSession` and `forkSession` were defined in both `client.ts` and `sessionStore.ts`, and called nonexistent backend endpoints (`POST /api/v2/sessions/{id}/reopen` and `POST /api/v2/sessions/{id}/fork`). These would always return 404 at runtime.

## Root Cause
The functions were defined but never imported or called by any frontend component. They were dead code added in anticipation of future features that were never built.

## Files Changed
| File | What changed |
|------|-------------|
| `frontend/src/api/client.ts` | Removed `reopenSession()` and `forkSession()` functions |
| `frontend/src/stores/sessionStore.ts` | Removed interface declarations and implementation blocks |

## What Was Done
Removed both dead functions from the API client and the session store. The unused endpoints were never called from any UI component, so no functionality is lost.

## Verification
- [x] Frontend builds without errors (`vite build` passed)
- [x] No remaining references to `reopenSession` or `forkSession` in src/
