# Scenario 05: Session Switch Toast Notification

## ID
`SCENARIO-05`

## Name
Session Switch During Loading — Toast Notification

## What It Tests
- Cond-12/13: User sends message → switches sessions during loading
- Response saves to original session in backend
- Toast notification appears: "Response received in session {title}"
- User clicks toast → navigates back to original session
- No UI corruption (turns of current session not overwritten by old response)

## Why This Matters
Without this, responses would go to the wrong session or be lost entirely. The toast pattern lets users multitask across sessions.

## Preconditions
- Backend running
- Frontend running
- Need at least 2 sessions (create via UI)

## Steps

### Step 1 — Create two sessions
| Action | Expected |
|--------|----------|
| Create Session A | Session A active |
| Attach dataset, send a message | Session A has 1 turn |
| Create Session B | Session B active |

### Step 2 — Send message from Session B, then quickly switch
| Action | Expected |
|--------|----------|
| Switch to Session A | Session A active |
| Attach dataset, type message, click Send | `loading: true`, UI locked |
| While loading, click Session B in sidebar | `switchSession()` called → Session B loads |

### Step 3 — Verify toast appears
| Action | Expected |
|--------|----------|
| Wait for response to arrive | Toast notification appears: "Response received in session {session A title}" |
| Check toast UI | Shows message + session title + dismiss × |
| Check toast visibility | Animates in from right, positioned bottom-right |

### Step 4 — Click toast to navigate back
| Action | Expected |
|--------|----------|
| Click the toast | Dismiss toast, call `switchSession(sessionA_id)` |
| Check Session A | New turn visible with the response |

### Step 5 — Test auto-dismiss
| Action | Expected |
|--------|----------|
| Wait 8 seconds | Toast auto-dismisses |
| Check ToastContainer | No toasts visible |

### Step 6 — Test dismiss ×
| Action | Expected |
|--------|----------|
| Trigger another toast | |
| Click × on the toast | Toast dismissed immediately |

### Step 7 — Verify no UI corruption
| Action | Expected |
|--------|----------|
| Switch back to Session B | Turns of Session B are intact, no cross-contamination |

## Bugs to Watch
- If response overwrites current session's turns → BUG
- If toast doesn't appear → BUG
- If toast navigates to wrong session → BUG
- If toast doesn't auto-dismiss → BUG (minor)

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
