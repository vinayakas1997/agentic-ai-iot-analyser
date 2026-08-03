# 05 — Progress-poll timer follows whatever session is "current," not the one that sent the message

**Severity:** High
**Status:** fix applied, needs test

## Explanation

`agentic-project/frontend/src/stores/sessionStore.ts`, the progress-poll
timer (around lines 352-359, `progressTimer`) reads `get().sessionId` on
every tick rather than capturing the session id that originated the
in-flight request. There is a separate `origSessionId` guard used elsewhere
(lines ~392-398) for a different check, but the timer's polling target
itself is not pinned to it.

**Failure scenario:** user sends a long-running query in session A, then
switches to a different, already-existing session B before A's processing
finishes. Because the timer reads the *current* `sessionId` on each tick, it
starts calling `api.getProgress(B, ...)` and writing whatever progress
record exists for B into the shared `progressSteps` field. Since
`ProcessingPanel` reads `progressSteps` from the same global store, it can
display B as "processing" with steps that don't belong to any request the
user actually made in B — confusing the user about which session is
actually busy.

## Files touched (to fix)

- `agentic-project/frontend/src/stores/sessionStore.ts`
  - Capture the originating session id in a local const when the poll timer
    is started (from the same request that kicked off `sendUserMessage`),
    and always poll `api.getProgress` against that captured id, not
    `get().sessionId`.
  - When the user switches away from the originating session, either keep
    polling in the background scoped to the original id (and route the
    result into per-session state rather than a single shared
    `progressSteps` field), or clearly indicate progress is for a
    different, non-visible session.

## Test plan

1. Send a message in session A that takes several seconds to process
   (e.g. a template with multiple queries).
2. Immediately switch to session B (a different, already-existing session).
3. Observe `ProcessingPanel`.
   - **Before fix:** panel may show "processing" steps unrelated to any
     action taken in B.
   - **After fix:** panel either shows nothing for B, or clearly attributes
     the progress to session A.
4. Switch back to A and confirm progress/results still show up correctly
   once processing completes.

## Current status

Fix applied in `agentic-project/frontend/src/stores/sessionStore.ts`
(`sendUserMessage`'s `progressTimer`): the poll callback now checks
`get().sessionId !== origSessionId` and bails out instead of polling
whatever session is currently displayed, and calls
`api.getProgress(origSessionId, ...)` (pinned) instead of a live-read
session id. The `set({ progressSteps })` write is additionally guarded by
the same check right before it runs. `tsc --noEmit` passes. Needs the
manual test plan above (send in session A, switch to session B mid-flight)
executed in the browser.
