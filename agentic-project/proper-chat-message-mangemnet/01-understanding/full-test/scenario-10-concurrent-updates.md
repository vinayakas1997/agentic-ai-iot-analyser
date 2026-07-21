# Scenario 10: Concurrent Updates & Race Conditions

## ID
`SCENARIO-10`

## Name
Race Conditions, Dual State Stores, and Concurrent UI Actions

## What It Tests
- Dual `completedActions` state: Zustand store + local `useState` — must stay in sync
- Dual `chatQueryResults` state: Zustand store + local `useState` — must stay in sync
- Adding aim via TurnBubble + removing via OutputPanel simultaneously
- Running SQL while summary is in progress
- `persistTurns` called while `sendUserMessage` is in-flight
- Zustand's synchronous `setState` vs React batching

## Why This Matters
Race conditions and state sync bugs are the hardest to catch. The dual-state pattern (Zustand + local `useState`) is inherently fragile and must be proven correct under concurrent operations.

## Preconditions
- Backend running
- Frontend running
- Fresh session with dataset + aim attached

## Steps

### Step 1 — Verify completedActions dual state
| Action | Expected |
|--------|----------|
| Run SQL on an aim | Both `storeCompletedActions` and local `completedActions` updated |
| Check immediately after | Both have `{ aim_name: turnId }` |
| Remove via × button | `handleRemoveCompletedAction()` removes from both |
| Check both stores | Both no longer have the entry |

### Step 2 — Verify state sync under rapid operations
| Action | Expected |
|--------|----------|
| Quickly: run SQL → remove completed action → run SQL again on same aim | |
| Check `completedActions` | Final state should have the new turnId, not the old one |
| Check `chatQueryResults` | Should have results from both SQL runs (different keys) |

### Step 3 — OutputPanel add + TurnBubble toggle race
| Action | Expected |
|--------|----------|
| Add aim via OutputPanel "+ Add" | `selectedAims` updated via `useSessionStore.setState` |
| Simultaneously toggle same aim via TurnBubble | Zustand handles both — no corruption |
| Check final `selectedAims` | Should have exactly 1 entry for that aim (idempotent add) |

### Step 4 — SQL while summary is in progress
| Action | Expected |
|--------|----------|
| Send 5 messages to trigger summary (2s debounce) | |
| Immediately run SQL (before summary completes) | `handleRunAimSql` fires independently |
| Check both complete | Summary API call + execute-query API call both finish |
| Check `persistTurns` called | Called after SQL completes (line 371, 398). At this point, summary may or may not have updated `contextSummaries` in the store. `persistTurns` reads latest Zustand state, so it will include whatever state is current, including the summary if it completed first. |

### Step 5 — Zustand synchronous vs React batching
| Action | Expected |
|--------|----------|
| In `handleRunAimSql`, after `setState` for `completedActions`, immediately read it back | `useSessionStore.getState().completedActions` should have the new entry (Zustand `setState` is synchronous) |
| Check that `persistTurns` called after `setState` reads correct data | Yes — `getState()` always returns latest |

### Step 6 — `useEffect` on `[sessionId]` closure test
| Action | Expected |
|--------|----------|
| Check the `useEffect` at line 415: it uses `chatQueryResults` and `storeCompletedActions` in its body but NOT in the deps array | |
| If `sessionId` doesn't change | This effect won't re-run. But `handleRunAimSql` manually updates both local and store anyway. Verify no stale closures. |

## Bugs to Watch
- **B2:** OutputPanel remove doesn't detach orphaned datasets → combined with TurnBubble add, the dataset store could end up with orphaned entries
- Verify that `handleRemoveCompletedAction` also removes the aim from `selectedAims` (it does via `setState` at line ~207)
- Check if the `useEffect` at line 415 (restores local state on session change) has stale closure issues with `chatQueryResults` / `storeCompletedActions`

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
