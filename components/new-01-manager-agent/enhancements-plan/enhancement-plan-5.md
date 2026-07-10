# Enhancement Plan 5 — Confirm Detection False Positives & Single Point of Entry

## Issue Summary

The plan confirmation system had two problems:

1. **Over-permissive routing:** `is_confirm_message` in `routing.py` used word-token matching (`word in user_msg.split()`), causing false positives. Messages like `"I don't want to go with that"` contained the token `"go"` and were incorrectly routed to `detect_confirm`.

2. **No helpful redirect:** When users typed sentences containing confirm words (e.g., `"I want to proceed with this plan"`), the system either falsely confirmed or wasted a turn before falling back to `extract_slots`. No guidance was provided on how to properly confirm.

## Root Cause

The original `is_confirm_message` function:
```python
def is_confirm_message(state: ManagerState) -> bool:
    if state.get("phase") != "plan":
        return False
    user_msg = (state.get("user_message") or "").lower().strip()
    return any(word == user_msg or word in user_msg.split() for word in _CONFIRM_WORDS)
    # "I don't want to go with that".split() contains "go" → FALSE POSITIVE
```

This was documented in `enhancement-plan-2.md` as Issue #6 and Issue #12, but only partially fixed (the decision layer `detect_confirm` was fixed, but the routing layer `is_confirm_message` was not).

## Proposed Solution

### Single Point of Entry for Plan Confirmation

Only two methods should finalize a plan:
1. Clicking the **"Go — proceed"** button in the UI
2. Typing an exact confirm word: `go`, `confirm`, `yes`, `proceed`, `ok`

### Three-Layer Routing

| Layer | Function | Behavior |
|-------|----------|----------|
| Exact match | `is_confirm_message` | Returns `True` only for exact single-word matches |
| Contains word | `is_confirm_like_message` | Returns `True` if message contains any confirm word |
| Otherwise | — | Routes to `extract_slots` for normal intent extraction |

### Redirect Message

When a user types a sentence containing a confirm word but not an exact match, show:
> "I'm in plan mode. To confirm this plan, please press the **Go — proceed** button or type exactly: go, confirm, yes, proceed, ok"

## Files to Modify

| File | Change |
|------|--------|
| `backend/agents/manager/routing.py` | Fix `is_confirm_message`, add `is_confirm_like_message`, update `route_after_inject` |
| `backend/agents/manager/nodes/confirm_redirect.py` | New node for redirect message |
| `backend/agents/manager/nodes/__init__.py` | Export `confirm_redirect` |
| `backend/agents/manager/graph.py` | Add `confirm_redirect` node and edges |
| `backend/agents/manager/tests/test_routing.py` | Update and add tests |

## Test Cases

### Should confirm (exact match)
- `"go"` → `detect_confirm`
- `"confirm"` → `detect_confirm`
- `"yes"` → `detect_confirm`
- `"proceed"` → `detect_confirm`
- `"ok"` → `detect_confirm`

### Should show redirect message (contains word)
- `"go with this plan"` → `confirm_redirect`
- `"I want to proceed"` → `confirm_redirect`
- `"yes please"` → `confirm_redirect`
- `"I don't want to go with that"` → `confirm_redirect`

### Should extract intent (no confirm word)
- `"show me options"` → `extract_slots`
- `"change the date"` → `extract_slots`
- `"what are the options"` → `extract_slots`

## Expected Behavior After Fix

| User Input | Before | After |
|------------|--------|-------|
| `"go"` | Confirm ✓ | Confirm ✓ |
| `"go with this plan"` | Confirm ✗ (bug) | Redirect message |
| `"I want to proceed"` | Confirm ✗ (bug) | Redirect message |
| `"I don't want to go"` | Confirm ✗ (bug) | Redirect message |
| `"change the date"` | Extract intent ✓ | Extract intent ✓ |

## Effort

**30 minutes** — Routing fix, new node, graph update, tests

## Priority

**High** — Prevents false plan finalization, improves UX with clear guidance
