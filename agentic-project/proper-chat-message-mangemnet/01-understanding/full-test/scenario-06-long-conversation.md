# Scenario 06: Long Conversation & Summary Triggers

## ID
`SCENARIO-06`

## Name
Summary Triggers at 5-Turn Intervals and Enrichment Block Growth

## What It Tests
- RESEARCH mode: per-tag summary triggers at every 5 turns per tag (`aim:X`, `dataset:Y`)
- SUMMARY mode: global `__all__` summary trigger at every 5 total turns
- 2s debounce on summary trigger
- Idempotency check on backend (returns existing summary if timestamps already covered)
- 5s frontend timeout fallback (hides "Summarizing..." after 5s)
- Enrichment block includes `[Summary]` entries for covered turns + `[Turn]` entries for uncovered
- Token budget (max 4000 chars): older entries dropped when exceeded

## Why This Matters
Summary triggers are the core of the token-reduction strategy. If they don't fire correctly, the enrichment block grows unbounded and the LLM context window fills with redundant history.

## Preconditions
- Backend running
- Frontend running
- Fresh session with dataset attached
- LLM available

## Steps

### Step 1 — RESEARCH mode: send 5 messages with same aim
| Action | Expected |
|--------|----------|
| Attach aim `A` | |
| Send message 1–4 | No summary trigger (not at 5 yet) |
| Send message 5 | Summary trigger fires for `aim:A` after 2s debounce |
| Check Network tab | `POST /summarize-context` with `tag: "aim:A"`, `turn_timestamps: [last 5 timestamps]` |

### Step 2 — Verify summary created
| Action | Expected |
|--------|----------|
| Check Zustand | `contextSummaries["aim:A"]` has 1 entry with `summary`, `turn_timestamps`, `created_at` |
| Check "Summarizing..." indicator | Shows during API call, disappears after response |
| Check idempotency | If same tag triggered again with same timestamps, backend returns existing without calling LLM |

### Step 3 — Send 5 more messages (10 total)
| Action | Expected |
|--------|----------|
| Send messages 6–10 | Second summary trigger for `aim:A` at message 10 |
| Check `contextSummaries["aim:A"]` | Has 2 entries (turns 1–5 and turns 6–10) |

### Step 4 — Verify enrichment block structure
| Action | Expected |
|--------|----------|
| Send message 11 | Enrichment block includes `[Summary: aim:A]` × 2 + `[Turn: ...]` for messages 11 |
| Check backend logs | "Building enrichment block" shows summary entries + unsummarized turns |

### Step 5 — SUMMARY mode: global summary
| Action | Expected |
|--------|----------|
| Switch to SUMMARY mode | |
| Send 5 messages (no attachments) | Global summary trigger for `__all__` at message 5 |
| Check `contextSummaries["__all__"]` | Has 1 entry covering all 5 timestamps |
| Send message 6 | Enrichment block shows `[Summary: __all__]` + `[Turn]` for message 6 |

### Step 6 — Token budget overflow
| Action | Expected |
|--------|----------|
| Send enough messages to exceed ~4000 tokens of enrichment | |
| Check enrichment block | Older entries (summaries or turns) dropped, newer entries kept |
| Check "Token budget exceeded" log | Backend logs when it stops appending |

## Bugs to Watch
- **B3:** `handleRunAimSql` creates synthetic turns with `created_at = UUID` (not ISO timestamp). If these turns get counted by the summary trigger, the `% 5` check counts them, but the `turn_timestamps` sent to the backend will be UUIDs, not ISO timestamps. The backend looks up turns by comparing timestamps — UUIDs won't match any turn, causing "No matching turns found" error.
- Verify debounce: send 2 messages quickly — only one summary trigger should fire (after 2s from the second message).
- Verify 5s timeout: if backend returns 502 (LLM failure), the "Summarizing..." indicator should disappear after 5s.

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
