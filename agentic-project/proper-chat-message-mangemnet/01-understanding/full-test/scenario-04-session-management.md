# Scenario 04: Session Management

## ID
`SCENARIO-04`

## Name
Create, Switch, Bootstrap, and New Session Flows

## What It Tests
- `bootstrap()` with existing sessions: most recent loaded, all state restored
- `switchSession()`: dataset store cleared, turns/proposals/summaries restored
- `newSession()`: all state cleared including `aimProposals`, `contextSummaries`, `enrichmentMode`
- Auto-naming on first message
- Dataset store clear behavior difference between `bootstrap()` and `switchSession()`

## Why This Matters
Session management is critical for usability. Users rely on switching between sessions to compare analyses. State corruption during session switch would cause data loss or incorrect displays.

## Preconditions
- Backend running
- Frontend running
- Multiple sessions with different data in each

## Steps

### Step 1 — Create Session A with data
| Action | Expected |
|--------|----------|
| Open app → auto-creates session | Session A created |
| Attach dataset, aim, send 2 messages | Session A has turns, proposals, summaries |
| Run SQL on one aim | Session A has `chatQueryResults`, `completedActions` |

### Step 2 — Create Session B
| Action | Expected |
|--------|----------|
| Click +New Session | `newSession()` called → all state cleared |
| Check Zustand | `turns: []`, `selectedAims: []`, `aimProposals: []`, `contextSummaries: {}`, `enrichmentMode: "research"` |
| Switch to SUMMARY mode | |
| Attach different dataset, send 1 message | Session B has different data than Session A |

### Step 3 — Switch back to Session A
| Action | Expected |
|--------|----------|
| Click Session A in sidebar | `switchSession()` called |
| Check dataset store | Should be cleared first (via `clear()`) then re-populated from Session A's `selected_aims` |
| Check turns | Restored with all 2+ messages |
| Check `chatQueryResults` | Restored with SQL results |
| Check `completedActions` | Restored with completed action AIM → turnId mapping |
| Check `enrichmentMode` | Restored to "research" (what Session A was using) |
| Check `contextSummaries` | Restored with any summaries |

### Step 4 — Refresh page (bootstrap)
| Action | Expected |
|--------|----------|
| Refresh | `bootstrap()` fetches session list, loads most recent (Session A) |
| Check dataset store | **B4: NOT cleared before restore** — if stale data from previous lifecycle was present, it persists |
| Check all state matches | Same as Step 3 checks |

## Bugs to Watch
- **B4:** `bootstrap()` does NOT call `datasetStore.clear()` before restoring, but `switchSession()` does. If `bootstrap()` runs when the dataset store has stale entries from a cached page, the restored datasets will be on top of stale ones. This could cause phantom attached datasets.
- Verify `switchSession()` resets `executionEvents` to `[]` (it does at line ~233).
- Verify `newSession()` clears `contextSummaries` and `enrichmentMode` (it should per Phase 1 AGENTS.md).

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
