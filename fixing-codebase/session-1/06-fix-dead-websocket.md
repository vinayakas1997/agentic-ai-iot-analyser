# Fix 6: Remove dead WebSocket code (MEDIUM)

**Status:** DONE

## Bug Description
WebSocket infrastructure was fully built but never used: 2 hook files (255 total lines of code), `wsStatus` state in sessionStore, and `/ws` nginx proxy config — all pointing to a WebSocket endpoint that doesn't exist in the backend.

## Root Cause
The WebSocket hooks were written for real-time execution event streaming but were never imported or called by any frontend component. The backend has no WebSocket handler.

## Files Changed
| File | What changed |
|------|-------------|
| `frontend/src/hooks/useWebSocket.ts` | Deleted (81 lines, never imported) |
| `frontend/src/hooks/useWorkspaceSocket.ts` | Deleted (174 lines, never imported) |
| `frontend/src/stores/sessionStore.ts` | Removed `wsStatus` state, interface, and `setWsStatus` action |
| `frontend/nginx.conf` | Removed `/ws` location block proxying to nonexistent WebSocket endpoint |

## What Was Done
1. Deleted both unused WebSocket hook files
2. Removed `wsStatus` state (interface, initial value, and setter) from sessionStore — it was never displayed in the UI
3. Removed `/ws` proxy block from nginx.conf — pointed to an endpoint that doesn't exist

## Verification
- [x] Frontend builds without errors (`vite build` passed)
- [x] Frontend container rebuilt and restarted (nginx.conf change requires rebuild)
- [x] No remaining references to `wsStatus`, `useWebSocket`, or `useWorkspaceSocket` in src/

## Notes
If real-time WebSocket support is needed in the future, the infrastructure should be rebuilt with:
1. A backend WebSocket handler (currently none exists)
2. Proper Docker env vars for the WS URL
3. Only the specific events that are needed
