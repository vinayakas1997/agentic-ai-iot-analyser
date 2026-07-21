# Enhancement Plan 4 — "More Options" Duplication & Endless Repeat Prevention (2026-07-09)

## Overview

When a user repeatedly clicks **"More options"** (or **"See more options"**) to generate alternative analysis plans, the system may fall into an **endless repetition loop** — showing the same or very similar proposals without meaningful variety, and with no feedback that exploration has been exhausted.

---

## Current Behavior

### How "More options" works

Each click of "More options" sends the user message `"more options"` to the backend, which:

1. `slot_inventory.py:638` — `_wants_explore_aims_fallback()` detects it via substring match and sets `aim_exploration.action = "propose"`
2. `routing.py:96` — Routes to `"propose_or_refine_plans"`
3. `explore_aims.py:212` — `propose_or_refine_plans()` calls the LLM to generate 3 fresh proposals
4. **Old proposals are replaced** with the newly generated ones (line 326)

### The duplication problem

| Scenario | Risk |
|---|---|
| Click "More options" 5+ times | LLM keeps generating — likely repeats same ideas after 3-4 batches |
| LLM returns < 3 proposals | Fallback silently reuses the **exact same old proposals** (line 332-334) |
| Proposal A from batch 1 reappears in batch 5 | Only "distinct from registry aims" instruction — no cross-batch dedup |
| No counter/limit | User can click endlessly with no "explored all angles" message |

### The stale fallback (worst case)

```python
# explore_aims.py:332-334 — Silent revert to existing proposals
if len(proposals) < 3 and existing:
    proposals = existing   # Shows identical cards, no message to user
```

User clicks "More options" → sees identical proposals → clicks again → sees them again → infinite loop.

---

## Root Causes

### 1. No history tracking across batches
Only the **last batch** (`analysis_proposals`) is saved. Previously shown proposals from batches 1, 2, or 3 are lost — the LLM can't avoid repeating them.

### 2. Weak dedup prompt instruction
The prompt (`propose_analysis_plans.md`) only says:
```
- On action propose: return exactly 3 distinct proposals beyond registry suggested aims where possible.
```
This targets **registry suggestions**, not **previously generated proposals**.

### 3. No exhaustion limit
There is no counter tracking how many times "propose" has been called in the current exploration cycle. No mechanism to say "I've explored all angles."

### 4. Silent fallback on stale generation
When the LLM fails to produce enough fresh proposals, the fallback silently shows the **old proposals** with no indication to the user.

---

## Proposed Fixes

### Fix 1 — Track `explore_iteration` and `seen_proposal_titles` in state

Add two new fields to `state.py::ManagerState`:

```python
explore_iteration: int           # 0-based counter of "more options" clicks
seen_proposal_titles: list[str]  # ALL proposal titles shown in this cycle
```

### Fix 2 — Add exhaustion check in `propose_or_refine_plans`

Before calling the LLM, check the iteration counter:

```python
MAX_EXPLORE = 4
if action == "propose":
    if iteration >= MAX_EXPLORE:
        return exhausted message → "I've explored all the analysis angles..."
    iteration += 1
```

### Fix 3 — Pass `seen_proposal_titles` to the prompt

Pass the full history to the prompt with a strong dedup instruction:

```markdown
Previously shown proposals (NEVER repeat these titles or aims — generate fresh):
{seen_proposal_titles_json}
```

### Fix 4 — Fix the stale fallback

On 2nd+ iteration, if LLM returns < 3 proposals, show the exhausted message instead of silently reusing old ones:

```python
if len(proposals) < 3 and existing and iteration <= 1:
    proposals = existing       # First attempt: allow fallback
elif len(proposals) < 3 and existing and iteration > 1:
    return exhausted message   # Repeat: show exhausted
```

### Fix 5 — Reset on plan selection

When user selects a plan (`merge_proposals_to_plan`), reset the counters so a new exploration cycle can start fresh:

```python
"explore_iteration": 0,
"seen_proposal_titles": [],
```

---

## Files to Modify

| File | Change |
|------|--------|
| `agents/manager/state.py` | Add `explore_iteration` + `seen_proposal_titles` fields |
| `agents/manager/nodes/explore_aims.py` | Add exhaust check, tracking, fixed fallback, reset in `merge_proposals_to_plan` |
| `agents/manager/prompts/propose_analysis_plans.md` | Add `{seen_proposal_titles_json}` + updated dedup rule |

---

## Behavior After Fix

```
1st "More options" → LLM generates batch A (3 proposals) — saves titles to seen
2nd "More options" → LLM sees A's titles → generates B (must avoid A's titles)
3rd "More options" → LLM sees A+B titles → generates C
4th "More options" → LLM sees A+B+C titles → generates D
5th "More options" → iteration >= 4 → "I've explored all the analysis angles..."
                                  ↓
User selects a plan → counters reset → can explore again from scratch
                                  ↓
LLM returns < 3 on 2nd+ click → exhausted message, not silent reuse
```

---

## Verification Checklist

- [ ] Click "More options" 5 times — 5th shows exhausted message, not more proposals
- [ ] Each batch has unique titles (no repeats from previous batches)
- [ ] LLM returns < 3 on 2nd click → exhausted message, not silent fallback to old cards
- [ ] Select a plan after exhaustion → counters reset → can explore again
- [ ] "More options" from plan mode (after `merge_proposals_to_plan`) starts a fresh cycle
- [ ] No regression on first-time "More options" — still shows 3 fresh proposals
- [ ] Refine action (tweaking existing plans) does not count as a "propose" iteration
- [ ] Frontend no additional changes needed — exhausted message renders as markdown naturally
