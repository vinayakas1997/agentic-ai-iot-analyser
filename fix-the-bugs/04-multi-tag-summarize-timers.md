# Fix 04 — Schedule summarize timers per tag (not one shared timer)

## Error

Auto-summarize used a single `summaryTimerRef`. The loop over eligible tags **overwrote** the timeout each iteration, so only the **last** tag was scheduled. Other tags relied on effect re-runs (cascading), which was flaky and delayed.

## Fix

Replaced with `summaryTimersRef: Map<tag, timeout>`. Each eligible uncovered tag gets its own 2s timer. Timers for tags that become covered / in-flight are cleared. Unmount clears all timers.

## Files touched

- `agentic-project/frontend/src/sections/ChatSection.tsx`

## Test / verification

- Code review: Map-based timers; no single overwritten ref.
- Multiple aim/dataset tags at 5 turns each can schedule in parallel without waiting for cascade.
