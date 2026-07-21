# Scenario 07: Enrichment Block Edge Cases

## ID
`SCENARIO-07`

## Name
Enrichment Block Edge Cases — Guards, Empty State, Token Budget

## What It Tests
- RESEARCH mode guard: no attachments → static message, no LLM call
- RESEARCH mode: attach aim only (no dataset) → enrichment from aim's context
- SUMMARY mode guard behavior with no datasets (see B1)
- Fresh session with no summaries → empty enrichment block → falls back to history path
- Token budget exceeded → oldest entries dropped

## Why This Matters
The enrichment block builder has multiple guard clauses and early returns. Each edge case must be tested to ensure the system degrades gracefully instead of crashing or producing wrong results.

## Preconditions
- Backend running
- Frontend running
- Fresh session

## Steps

### Step 1 — RESEARCH mode, no attachments, no datasets
| Action | Expected |
|--------|----------|
| Ensure RESEARCH mode, no datasets selected, no aims attached | |
| Type a message and send | Guard at `api.py:553-554`: `enrichment_mode == "research"` AND `not attached_aims` AND `not dataset_names` → true |
| Check response | Returns static "Please attach a dataset or aim to start" — **no LLM call** |
| Check backend logs | No "Building enrichment block" log |

### Step 2 — RESEARCH mode, aim only (no dataset)
| Action | Expected |
|--------|----------|
| Attach an aim that has associated datasets | `useAim()` should also attach the aim's datasets via `storeAddMultiple` + `storeAttachMultiple` |
| If aim has NO datasets | This may not be possible since aims reference datasets. Test by manually setting `attached_aims` in the send call. |
| Send message | Enrichment block built from aim's context summaries + turns |

### Step 3 — Fresh session, no summaries
| Action | Expected |
|--------|----------|
| Start a brand new session, attach dataset, send message | |
| Check `contextSummaries` | Empty `{}` — no summaries exist yet |
| Check enrichment block | `build_enrichment_block()` has no summaries to include, only raw `[Turn]` entries |
| Verify no crash | Enrichment block built successfully from raw turns |

### Step 4 — Token budget exceeded
| Action | Expected |
|--------|----------|
| Send many messages (15+) to accumulate both summaries and raw turns | |
| Send one more message | Enrichment block builder iterates tags, adds summaries + turns |
| Check backend log for "Token budget exceeded" | When `estimate_tokens(combined) > 4000`, older entries dropped |
| Verify response | Message still processed normally (truncated enrichment is not an error) |

### Step 5 — SUMMARY mode, no datasets (B1 test)
| Action | Expected |
|--------|----------|
| Switch to SUMMARY mode, no datasets, no aims | |
| Send a message | |
| **If B1 exists:** | Returns static "Please select at least one dataset" — SUMMARY mode broken |
| **If B1 fixed:** | Enrichment block empty or built from global summaries, LLM called with SUMMARY prompt |

## Bugs to Watch
- **B1:** SUMMARY mode with no datasets → blocked by `api.py:556` guard (dataset check is mode-agnostic)
- **B5:** If `generate_aim` import fails at `api.py:12`, any research endpoint call crashes
- Check that `build_enrichment_block` handles empty `attached_aims` + empty `attached_datasets` gracefully in both modes
- Check that `estimate_tokens()` uses ~4 chars/token heuristic (verify against actual tokenization)

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
