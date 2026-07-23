# Scenario 08: Error Handling

## ID
`SCENARIO-08`

## Name
Error Handling — Validation, Conflicts, and Backend Errors

## What It Tests
- Cond-1: Guard returns early when nothing attached in RESEARCH mode
- Cond-10: Error message shown appropriately
- 400 validation errors (empty message, missing session)
- 404 errors (invalid session ID)
- 409 conflict errors (version mismatch)
- Error does not corrupt UI state

## Preconditions
- Backend running
- Frontend running
- Fresh session

## Steps

### Step 1 — Send without attachments (Cond-1)
| Action | Expected |
|--------|----------|
| Ensure no datasets/aims attached | `storeAttached.length === 0`, `selectedAims.length === 0` |
| Type message and send | Backend returns early: "Please attach a dataset or aim, or switch to SUMMARY mode." |
| Check no LLM call | No LLM API call made (fast response) |

### Step 2 — Send empty message
| Action | Expected |
|--------|----------|
| Click Send with empty input and no aims | Button should be disabled |
| If bypassed | Backend returns 400: "message is required" |

### Step 3 — Invalid session ID
| Action | Expected |
|--------|----------|
| Manually call API with fake session ID | 404 error returned |
| Frontend shows error | Error message displayed |

### Step 4 — 409 conflict (version mismatch)
| Action | Expected |
|--------|----------|
| Simulate concurrent update | `withRetry()` attempts 3 retries with exponential backoff |
| Check console | Retry logs visible |
| After 3 retries | Error shown to user |

### Step 5 — Error message display
| Action | Expected |
|--------|----------|
| Trigger an error | Error message shows in chat area or toast |
| Check message content | Describes what went wrong |
| Check UI | All buttons re-enabled after error (Cond-10) |

## Bugs to Watch
- If guard doesn't trigger for RESEARCH mode with no attachments → BUG
- If error message is vague or missing → BUG
- If buttons stay disabled after error → BUG

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
