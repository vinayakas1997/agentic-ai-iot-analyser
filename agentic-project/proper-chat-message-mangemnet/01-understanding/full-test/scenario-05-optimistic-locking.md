# Scenario 05: Optimistic Locking & 409 Retry

## ID
`SCENARIO-05`

## Name
Concurrent Modification Detection and Retry

## What It Tests
- Two rapid `sendMessage` calls → first succeeds, second gets 409 → retries with backoff
- `withRetry()` exponential backoff: 1s, 2s, 4s (3 attempts max)
- Summary `summarizeContext` + `sendMessage` race → one wins, other retries
- `executeQuery` retry on 409
- `updateSessionState` retry on 409
- Version column increments correctly on each write

## Why This Matters
Optimistic locking is the backbone of data integrity. Without it, concurrent requests would overwrite each other's changes, losing turns and summaries. Testing this specifically under race conditions is essential.

## Preconditions
- Backend running
- Frontend running
- Fresh session

## Steps

### Step 1 — Single message (baseline)
| Action | Expected |
|--------|----------|
| Send one message | Success, version incremented to 2 (was 1) |
| Check DB | `manager_sessions.version = 2` |

### Step 2 — Rapid double-send (simulated race)
| Action | Expected |
|--------|----------|
| Open two browser tabs with same session | Both have same `version` cached |
| In Tab A: send a message | Succeeds, version → 3 |
| In Tab B: immediately send a message | Gets 409 (version mismatch: Tab B expected 2, DB has 3) |
| Check Network tab | Tab B shows 409 response |
| Check retry | Tab B retries after 1s with fresh `sessionId` → succeeds on retry, version → 4 |

### Step 3 — Verify no data loss
| Action | Expected |
|--------|----------|
| Refresh both tabs | Both show all turns (both messages persisted) |
| Check `state_json.turns` | Has 3 entries (baseline + Tab A + Tab B) |

### Step 4 — Summarize-context race
| Action | Expected |
|--------|----------|
| Send 5 messages to trigger summary threshold | Summary trigger fires |
| While summary is in-progress, send another message | `sendMessage` and `summarizeContext` compete |
| Check backend logs | One gets 409, retries, both succeed eventually |
| Check version | Incremented by 2 (one for summary write, one for message write) |

### Step 5 — Retry exhaustion
| Action | Expected |
|--------|----------|
| Hold a session lock (manually increment version in DB) | |
| Attempt any write operation | Gets 409, retries 3 times (1s + 2s + 4s = 7s total), then fails |
| Check console | Error shown to user after all retries exhausted |

## Bugs to Watch
- `withRetry` in `client.ts` should retry ONLY on 409, not on 400/404/500
- Verify the retried request body is identical to the original (same message, same attached aims)
- `executeQuery` also has retry — verify it handles 409 correctly (it uses `withRetry` too)
- `updateSessionState` (PATCH) also has retry — but PATCH does NOT use optimistic locking on backend, so 409 should never occur. If it does, retry is harmless.

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
