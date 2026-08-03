# 10 — 15s session-list poller can overwrite freshly-updated session metadata with stale data

**Severity:** Low/Medium
**Status:** fix applied, needs test

## Explanation

`agentic-project/frontend/src/stores/sessionStore.ts`, `startPoller` (lines
~554-572), runs every 15 seconds and does:

```ts
sessionMeta: { ...(state.sessionMeta || {}), ...current }
```

where `current` comes from the lighter `listSessions()` endpoint (a list
item, not full session detail). Separately, `sendUserMessage` (lines
~402-410) sets fresher fields like `phase`/`status`/`mode` directly on
`sessionMeta` immediately after a message completes.

**Failure scenario:** user sends a message that flips a session's phase
(e.g. `"lines"` → `"aims"`). If the 15s poll tick lands shortly after, and
the backend's session-list index/read model hasn't caught up yet to reflect
the new phase, the poller's merge can briefly reset the displayed
phase/status back to the pre-message value, until the next poll tick
catches up — a flickering/regression of displayed session state that isn't
caused by any real backend inconsistency, just poll timing.

## Files touched (to fix)

- `agentic-project/frontend/src/stores/sessionStore.ts` (`startPoller`,
  lines ~554-572)
  - Track a "last updated" timestamp or version per session field set
    locally by `sendUserMessage`, and have the poller merge skip
    overwriting fields that were updated more recently than the poll
    response's data source, or debounce polling briefly after a local
    update.

## Test plan

1. Send a message that changes a session's `phase` (e.g. completing the
   "lines" step to move to "aims").
2. Observe the UI for the following ~15-20 seconds.
   - **Before fix:** phase/status may briefly flicker back to the old value
     when the poller ticks, before correcting itself on a later tick.
   - **After fix:** no flicker; locally-known-fresh fields aren't
     regressed by a stale poll response.
3. Confirm the poller still correctly picks up *externally* changed session
   state (e.g. changes made in another browser tab/session) after the
   normal 15s interval.

## Current status

Fix applied in `agentic-project/frontend/src/stores/sessionStore.ts`:
added a module-level `_lastLocalMetaUpdate` timestamp, stamped in
`sendUserMessage` right before it locally sets `sessionMeta.phase/status`.
`startPoller`'s 15s tick now skips merging the list endpoint's `current`
data into `sessionMeta` if a local update happened within the last 5
seconds, avoiding the flicker-back-to-stale-value window. `tsc --noEmit`
passes. Needs the manual test plan above (send a message that flips phase,
watch for ~20s) executed in the browser.
