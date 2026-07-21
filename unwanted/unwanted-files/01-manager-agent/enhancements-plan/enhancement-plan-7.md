# Enhancement Plan 7 — Fix Edit/Fork/New Button State Leaks & Navbar Sync (2026-07-09)

## Overview

When a session completes (plan is fixed), three buttons appear: **Edit**, **Fork**, and **New**. The Edit and Fork buttons have broken behavior due to stale state leaking across sessions and the navbar not refreshing after operations.

---

## Current Behavior

### Edit button — incorrectly hidden

1. Session A completes, planner starts → `planner.start` event pushed to `executionEvents`
2. User clicks Fork → switches to new session B
3. `executionEvents` still contains session A's `planner.start` event
4. `plannerStarted` evaluates to `true` (ChatSection.tsx line 108)
5. **Edit button is replaced with warning**: "Planner has already begun — cannot edit this session"
6. User cannot edit session B even though its planner hasn't started

Same issue affects **New** — creating a fresh session inherits stale execution events.

### Fork button — navbar doesn't update

1. User clicks Fork → `forkSession` creates a new session via API
2. `switchSession` loads the new session into the UI
3. **`refreshSessions()` is never called** → navbar dropdown doesn't show the new forked session
4. User must manually refresh the page to see the new session

### Reopen button — navbar doesn't update

1. User clicks Edit → `reopenSession` resets the session via API
2. State is updated locally
3. **`refreshSessions()` is never called** → navbar doesn't reflect the change

---

## Root Causes

| Issue | File | Root Cause |
|-------|------|------------|
| Stale `executionEvents` on switch | `sessionStore.ts:118-135` | `switchSession` doesn't clear `executionEvents` |
| Stale `executionEvents` on new | `sessionStore.ts:137-153` | `newSession` doesn't clear `executionEvents` |
| Navbar not updated after fork | `sessionStore.ts:212-224` | `forkSession` doesn't call `refreshSessions()` |
| Navbar not updated after reopen | `sessionStore.ts:189-210` | `reopenSession` doesn't call `refreshSessions()` |

---

## Proposed Changes

### Change 1 — Clear `executionEvents` in `switchSession`

Add `executionEvents: []` to the `set()` call so switching sessions starts with clean event state.

### Change 2 — Clear `executionEvents` in `newSession`

Add `executionEvents: []` to the `set()` call so new sessions start clean.

### Change 3 — Add `refreshSessions()` to `forkSession`

After `switchSession` completes, call `refreshSessions()` so the navbar shows the new forked session.

### Change 4 — Add `refreshSessions()` to `reopenSession`

After state is updated, call `refreshSessions()` so the navbar reflects the reopened session.

---

## Files to Modify

| File | Change |
|------|--------|
| `frontend/src/stores/sessionStore.ts` | Add `executionEvents: []` to `switchSession` and `newSession`; add `refreshSessions()` to `forkSession` and `reopenSession` |

---

## Behavior After Fix

```
Session A completes → Edit, Fork, New buttons appear

User clicks Fork:
  → New session created with previous plan
  → UI switches to new session
  → Navbar dropdown updates to show new session
  → Edit button correctly visible (no stale planner events)
  → Fork and New buttons also work correctly

User clicks Edit (on session where planner hasn't started):
  → Session reopens in planner mode
  → Existing plan pre-filled for editing
  → Navbar reflects the change

User clicks New:
  → Fresh session created
  → executionEvents cleared
  → No stale planner events from previous sessions
```

---

## Verification Checklist

- [ ] Fork creates new session and navbar dropdown updates
- [ ] Edit button shows when planner hasn't started (no stale events)
- [ ] Edit button hidden with warning when planner HAS started
- [ ] New session starts with clean executionEvents
- [ ] Switching sessions clears executionEvents
- [ ] Reopen session updates navbar
- [ ] No regression on existing quick-reply buttons
- [ ] TypeScript compiles with no errors
- [ ] Vite build succeeds
