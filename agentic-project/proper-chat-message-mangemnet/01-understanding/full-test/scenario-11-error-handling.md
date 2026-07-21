# Scenario 11: Error Handling Paths

## ID
`SCENARIO-11`

## Name
HTTP Error Codes, LLM Failures, and Graceful Degradation

## What It Tests
- 400: empty message, missing fields, invalid timestamps
- 404: session not found, dataset not found
- 409: optimistic locking conflict
- 502: LLM summarization failure (empty summary returned)
- 500: server error on task definition save
- LLM failure in `generate_chat_response` → returns error string (not crash)
- `call_llm` failure → returns `""` → `extract_aims` returns `[]` (not crash)
- Chart suggestions failure → falls back to rule-based → never blocks response
- Frontend 5s timeout on summary failure → hides "Summarizing..." without error

## Why This Matters
The system has multiple silent degradation paths. Each must be verified to ensure the user always gets a sensible response, even when LLM, DB, or network fail.

## Preconditions
- Backend running
- Frontend running
- Fresh session

## Steps

### Step 1 — 400 Bad Request: empty message
| Action | Expected |
|--------|----------|
| Type only whitespace and send | Frontend should guard at `handleSend` — but if whitespace passes, backend returns 400 |
| Check response | `{"detail": "message is required"}` |
| Check frontend | Shows error message to user |

### Step 2 — 404 Not Found: invalid session
| Action | Expected |
|--------|----------|
| Manually set `sessionId` to a non-existent UUID in browser console | |
| Try to send a message | `sendUserMessage` calls `sendMessage` → backend returns 404 |
| Check frontend | `withRetry` does NOT retry on 404 (only 409), so error shown immediately |

### Step 3 — 409 Conflict (already covered in scenario 05)
| Action | Expected |
|--------|----------|
| Rapid double-send | Second request gets 409, retried |
| Verify 409 is retried | `withRetry` catches 409, waits 1s, retries |
| Verify other codes NOT retried | 400, 404, 500 are not retried |

### Step 4 — 502 Bad Gateway: LLM summary fails
| Action | Expected |
|--------|----------|
| Block LLM endpoint or return empty from `summarize_turns` | |
| Trigger a summary (send 5 messages) | Backend returns 502 |
| Check frontend | 5s timeout fires → `summarizingTags` removes the tag → "Summarizing..." disappears |
| Check console | No error shown to user (silent degradation) |

### Step 5 — LLM fail in chat response
| Action | Expected |
|--------|----------|
| Block LLM endpoint or make `call_llm` return `""` | |
| Send a message | `generate_chat_response` tries LLM, fails |
| Check backend | Returns error message string like "I encountered an error..." — does NOT raise HTTP exception |
| Check frontend | Error message appears in chat as agent response |

### Step 6 — Chart suggestions failure
| Action | Expected |
|--------|----------|
| Block LLM or make `suggest_charts` fail | |
| Run SQL | SQL executes successfully |
| Check response | `chart_suggestions` should be `None` or use fallback rules |
| Check UI | Result shows without chart (chart section absent or shows fallback) |
| Verify no crash | Entire response still valid |

### Step 7 — 400: summarize-context no matching turns
| Action | Expected |
|--------|----------|
| Call `summarizeContext` with fake timestamps | Backend returns 400 "No matching turns found" |
| Check frontend | `triggerSummary` catches error, removes tag from `summarizingTags` |
| Verify "Summarizing..." hides | |

### Step 8 — 500: bucket/proceed server error
| Action | Expected |
|--------|----------|
| Call `POST /api/v2/bucket/proceed` with invalid session | |
| Check response | 500 with message truncated to 200 chars |
| (This endpoint is legacy — not part of main flow) | |

## Bugs to Watch
- `withRetry` should only retry on 409, not 400/404/500. Verify by looking at `client.ts` error handling.
- The 5s frontend timeout in `triggerSummary()` should always fire even if the API call succeeds quickly (it clears the timeout on success, so it only fires on failure/timeout).
- `call_llm` returns `""` on any exception — verify that `extract_aims_from_text("")` returns `[]` gracefully.
- `generate_chat_response` returns an error string, not a dict — verify the frontend can handle a string response vs expected dict format.

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
