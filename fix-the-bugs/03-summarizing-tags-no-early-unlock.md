# Fix 03 — Do not unlock summarizingTags after 5 seconds

## Error

`triggerSummary` started a **5s timeout** that removed the tag from `summarizingTags` while the summarize HTTP/LLM call was still in flight (often >5–30s). The auto-summarize effect then treated the tag as free and scheduled **another** summarize → duplicate LLM calls.

## Fix

Removed the 5s early unlock. The tag stays in `summarizingTags` until the request finishes (`finally` block), which already clears it on success or failure.

## Files touched

- `agentic-project/frontend/src/sections/ChatSection.tsx`

## Test / verification

- Code review: no `setTimeout(..., 5000)` unlock remains in `triggerSummary`.
- Tag is only removed in `finally` after `summarizeContext` settles.
