# Scenario 03: UI Locking During Loading

## ID
`SCENARIO-03`

## Name
UI Locking — All Actions Disabled During LLM Processing

## What It Tests
- Cond-7: User cannot detach AIM while Send is in progress
- Cond-8: User cannot detach dataset while Send is in progress
- Cond-9: User cannot send another message while one is in progress
- Cond-11: User cannot switch modes while Send is in progress
- After response (good or bad), all UI elements are re-enabled

## Why This Matters
One query at a time is the rule. Without UI locking, race conditions, duplicate turns, and confusing UX would occur.

## Preconditions
- Backend running (can use mock/slow response to test locking)
- Frontend running
- Fresh session with datasets attached

## Steps

### Step 1 — Attach dataset + aim
| Action | Expected |
|--------|----------|
| Select a dataset | Dataset attached |
| Click a suggested aim (if available) or type an aim manually | AIM appears in AimBar |

### Step 2 — Verify all buttons active before send
| Action | Expected |
|--------|----------|
| Check Send button | Enabled (has text or aims) |
| Check mode switch RESEARCH/SUMMARY | Both clickable |
| Check dataset detach × | Clickable (not locked) |
| Check AimBar remove × | Clickable |
| Check AimBar RUN | Clickable |
| Check TurnBubble toggles | Clickable |
| Check "Suggested by LLM" buttons | Clickable |

### Step 3 — Send a message
| Action | Expected |
|--------|----------|
| Click Send | Message sent, `loading: true` |
| Immediately try all buttons | |

### Step 4 — Verify ALL buttons disabled
| Action | Expected |
|--------|----------|
| Click Send again | Disabled |
| Click RESEARCH/SUMMARY toggle | Disabled (`cursor-not-allowed`, `opacity-50`) |
| Click dataset detach × | Disabled |
| Click AimBar remove × | Disabled |
| Click AimBar RUN | Disabled |
| Click TurnBubble toggle pills | Disabled |
| Click "Suggested by LLM" buttons | Disabled |

### Step 5 — After response arrives
| Action | Expected |
|--------|----------|
| Wait for response | All buttons re-enabled |
| Verify each button | Clickable again |

### Step 6 — Test with error response
| Action | Expected |
|--------|----------|
| Send invalid message (empty text) | Error occurs |
| Check buttons | Re-enabled after error |

## Bugs to Watch
- Any button that remains clickable during loading → BUG
- Any button that stays disabled after response → BUG
- Mode switch during loading should be disabled — if it's not, BUG

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
