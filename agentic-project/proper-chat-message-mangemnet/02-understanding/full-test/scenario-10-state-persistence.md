# Scenario 10: State Persistence

## ID
`SCENARIO-10`

## Name
State Persistence — Turns, Aims, Datasets, Mode

## What It Tests
- Turns saved correctly via `persistTurns()`
- `selectedAims`, `enrichmentMode` persisted
- `contextSummaries`, `chatQueryResults` persisted
- State restored on session load (`bootstrap()` / `switchSession()`)
- No data loss on refresh

## Preconditions
- Backend running
- Frontend running
- Fresh session

## Steps

### Step 1 — Create state
| Action | Expected |
|--------|----------|
| Attach dataset, send message | Turn created |
| Attach an aim | `selectedAims` populated |
| Switch to SUMMARY mode | Mode changed |

### Step 2 — Verify persistence
| Action | Expected |
|--------|----------|
| Check `PATCH` request | `turns`, `selected_aims`, `enrichment_mode` sent |
| Query DB | `manager_sessions.state_json` has all fields |

### Step 3 — Restore on session load
| Action | Expected |
|--------|----------|
| Refresh page | `bootstrap()` loads session |
| Check turns | Previous turns visible |
| Check mode | SUMMARY mode restored |
| Check aims | `selectedAims` restored |

## Bugs to Watch
- If data lost on refresh → BUG
- If `selectedAims` not restored → BUG

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
