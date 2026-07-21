# Scenario 09: State Persistence & Restore

## ID
`SCENARIO-09`

## Name
State Persistence (`persistTurns`), Bootstrap Restore, and Backward Compatibility

## What It Tests
- `persistTurns()` saves all state fields via `PATCH /sessions/{id}`
- `bootstrap()` restores: `turns`, `selectedAims`, `chatQueryResults`, `completedActions`, `contextSummaries`, `enrichmentMode`
- `switchSession()` restores: same as bootstrap + dataset store cleared
- Backward compat: old sessions without `result_uuid` on turns → falls back to `created_at`/`timestamp` key lookup
- `chatQueryResults` dual storage: Zustand store + local `useState`
- Shallow merge in `updateSession` (B6)

## Why This Matters
Data persistence is table stakes. If state doesn't survive a page refresh or session switch, the entire system is unreliable.

## Preconditions
- Backend running
- Frontend running
- Session with: 2+ turns, 1+ SQL result, 1+ summary, 1+ completed action, enrichment mode set

## Steps

### Step 1 — Verify what `persistTurns` saves
| Action | Expected |
|--------|----------|
| After running SQL, check Network tab | `PATCH /api/v2/sessions/{id}` fires |
| Check request body | Has: `turns`, `selected_aims`, `attached_datasets`, `output_results`, `chat_query_results`, `completed_actions`, `enrichment_mode`, `context_summaries` |
| Check each field is non-empty | Only persisted if truthy/non-empty (guards in `persistTurns()`) |

### Step 2 — Refresh page
| Action | Expected |
|--------|----------|
| Refresh | `bootstrap()` fetches session from `GET /api/v2/sessions/{id}` |
| Check turns | All turns restored with `created_at`, `aims`, `datasets`, `result_uuid` |
| Check `selectedAims` | As they were before refresh |
| Check `chatQueryResults` | As they were (state restored from `detail.state.chat_query_results`) |
| Check `completedActions` | Restored correctly |
| Check `contextSummaries` | All summary entries present |
| Check `enrichmentMode` | Same as before refresh |

### Step 3 — Verify backward compat (old session)
| Action | Expected |
|--------|----------|
| Manually create a session in DB with turns that have `timestamp` but no `result_uuid` | Simulates pre-Phase-1 session |
| Load that session | |
| Check TurnBubble rendering | Line 636: `queryResults[t.result_uuid ?? ""] \|\| queryResults[t.created_at ?? ""]` |
| Fallback path | If `result_uuid` is absent, falls back to `t.created_at` which should be the old `timestamp` key |

### Step 4 — Verify dual chatQueryResults
| Action | Expected |
|--------|----------|
| Run SQL | Both `chatQueryResults` (Zustand) and `queryResults` (local useState) updated |
| Check local state | `queryResults` used for rendering (TurnBubble line 636) |
| Check store | `chatQueryResults` used for persistence |
| Verify consistency | Both have same keys and values |

### Step 5 — Shallow merge test (B6)
| Action | Expected |
|--------|----------|
| Call `persistTurns()` which sends `{ turns, chat_query_results, context_summaries }` | |
| Check backend `PATCH` handler | `state.update(body.state)` — shallow merge |
| If `context_summaries` was previously nested | Shallow merge replaces the entire `context_summaries` key, not individual tags. This should be fine since `persistTurns` sends the entire `context_summaries` object. But if another caller does `updateSession({ state: { context_summaries: { "aim:X": [...] } } })`, it would **overwrite** other existing summary tags (e.g., `__all__`). |
| Verify no data loss | After multiple `persistTurns` calls, all summary tags still present |

## Bugs to Watch
- **B4:** `bootstrap()` doesn't clear dataset store — stale datasets could persist
- **B6:** Shallow merge in `updateSession` — if `persistTurns` sends partial state, previously saved fields could be overwritten with `undefined`. Check that `persistTurns` always sends the full `context_summaries` and `chat_query_results` objects.
- Verify that old sessions (pre-Phase-1) with `timestamp` instead of `created_at` on turns are handled gracefully. The turn mapping in `bootstrap()` at `sessionStore.ts` handles this with `t.created_at \|\| t.timestamp \|\| new Date().toISOString()`.

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
