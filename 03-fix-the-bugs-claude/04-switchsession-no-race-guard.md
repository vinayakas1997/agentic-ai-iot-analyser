# 04 — `switchSession` has no race/epoch guard, unlike `bootstrap()`

**Severity:** High
**Status:** fix applied, needs test

## Explanation

`agentic-project/frontend/src/stores/sessionStore.ts`, `switchSession`
(lines 235-298), fetches session detail via `api.getSession(id, uid)` and
then unconditionally calls `set({...})` with the result. `bootstrap()`
elsewhere in the same store uses a `_bootstrapEpoch` counter to discard
stale results if a newer bootstrap call started in the meantime —
`switchSession` has no equivalent check.

**Failure scenario:** user clicks session A, then quickly clicks session B
before A's `api.getSession` resolves. If A's request resolves *after* B's
(e.g. A's backend query is slower), A's `set({...})` call runs last and
overwrites `sessionMeta`, `turns`, `chatQueryResults`, etc. with session A's
data — even though the UI is currently supposed to be showing session B.
Additionally, `useDatasetStore.getState().clear()` and `addMultiple(...)`
(lines ~277-286) run per-call, so B's dataset attachments can be wiped by
A's late-arriving call.

## Files touched (to fix)

- `agentic-project/frontend/src/stores/sessionStore.ts`
  - Add an epoch/request-id counter for `switchSession`, mirroring
    `_bootstrapEpoch`: increment a counter before starting the fetch, capture
    its value in closure, and only apply `set({...})` / dataset store
    mutations if the counter is still current when the request resolves.

## Test plan

1. In the UI, create two sessions A and B with different attached datasets.
2. Throttle network (browser devtools) so `getSession` calls take a few
   seconds.
3. Click session A, then immediately click session B.
   - **Before fix:** depending on response timing, the app can end up
     showing session B's title in the header while displaying A's turns/
     datasets, or vice versa.
   - **After fix:** only the last-clicked session's data is ever applied,
     regardless of response order.
4. Add an automated test (e.g. with mocked `api.getSession` resolving out
   of order) asserting the store's final `sessionId`/`sessionMeta` matches
   the last-requested session.

## Current status

Fix applied in `agentic-project/frontend/src/stores/sessionStore.ts`:
added a module-level `_switchEpoch` counter (mirroring `_bootstrapEpoch`).
`switchSession` increments it before fetching, captures the value, and
checks it hasn't changed before every `set({...})` call and before the
`catch`/`finally` blocks — a superseded call's response is now discarded
instead of overwriting newer session state. `tsc --noEmit` passes. Needs
the manual test plan above (throttled network, rapid session switching)
executed in the browser.
