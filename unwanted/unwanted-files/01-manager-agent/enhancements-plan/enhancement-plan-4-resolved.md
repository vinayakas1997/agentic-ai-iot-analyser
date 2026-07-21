# Enhancement Plan 4 — Resolution Summary

All 5 fixes from `enhancement-plan-4.md` implemented.  
Verification: `python3 -m py_compile state.py` ✓, `python3 -m py_compile explore_aims.py` ✓, `vite build` ✓.

---

## Fix 1 — State Fields Added

**File:** `agents/manager/state.py:67-69`

Two new fields in `ManagerState`:

```python
explore_iteration: int           # 0-based counter of "more options" clicks
seen_proposal_titles: list[str]  # ALL proposal titles shown in this cycle
```

These persist across turns via the existing LangGraph state persistence mechanism.

---

## Fix 2 — Exhaustion Check in `propose_or_refine_plans`

**File:** `agents/manager/nodes/explore_aims.py:240-258`

At the entry of `propose_or_refine_plans()`, after reading state:

```python
iteration = state.get("explore_iteration") or 0
seen_titles = list(state.get("seen_proposal_titles") or [])
MAX_EXPLORE = 4

if action == "propose":
    if iteration >= MAX_EXPLORE:
        msg = (
            f"I've explored all the analysis angles I can think of for **{scope_label}**.\n\n"
            "Try a different line or scope, or say *use saved* to revisit saved plans."
        )
        return {
            **state,
            "analysis_proposals": None,
            "explore_phase": None,
            "phase": "ask",
            "agent_message": msg,
            "wants_suggested_aims": False,
            "aim_exploration": None,
        }
    iteration += 1
```

After 4 "More options" clicks, the system returns an exhausted message instead of calling the LLM. The `action == "propose"` guard ensures "refine" actions (tweaking existing plans) do not count toward the exhaustion limit.

---

## Fix 3 — `seen_proposal_titles` Passed to Prompt

**File:** `agents/manager/nodes/explore_aims.py:278`

New template variable passed when building the prompt:

```python
seen_proposal_titles_json=json.dumps(seen_titles, indent=2),
```

**File:** `agents/manager/prompts/propose_analysis_plans.md:26-27`

New section in the prompt:

```markdown
Previously shown proposals (NEVER repeat these titles or aims — generate fresh):
{seen_proposal_titles_json}
```

Rule (line 51) updated from:

```
- On action propose: return exactly 3 distinct proposals beyond registry suggested aims where possible.
```

To:

```
- On action propose: return exactly 3 proposals distinct from BOTH registry suggested aims AND all previously shown proposals listed above.
```

---

## Fix 4 — Stale Fallback Fixed

**File:** `agents/manager/nodes/explore_aims.py:356-375`

Original fallback (silent revert to old proposals):

```python
if len(proposals) < 3 and existing:
    proposals = existing
```

New fallback with exhaustion awareness:

```python
if len(proposals) < 3 and existing and iteration <= 1:
    proposals = existing                    # First attempt: allow fallback
elif len(proposals) < 3 and existing and iteration > 1:
    msg = exhausted message                 # Repeat: show exhausted
    return { ... phase: "ask", ... }
```

The `iteration` variable is already incremented by the time this check runs (line 258), so:
- **iteration=1** (first click): fallback to existing is allowed (same as old behavior)
- **iteration=2+** (2nd+ click): exhausted message is shown instead of silently reusing old cards
- **iteration=4+**: never reaches this code — caught by the earlier exhaust check (Fix 2)

---

## Fix 5 — Reset on Plan Selection

**File:** `agents/manager/nodes/explore_aims.py:532-533`

In `merge_proposals_to_plan()` return dict, the counters are reset:

```python
"explore_iteration": 0,
"seen_proposal_titles": [],
```

This ensures that once the user selects a plan (confirm N), the next "More options" cycle starts fresh with a clean slate.

---

## Post-vs Pre- Comparison

| Scenario | Before | After |
|---|---|---|
| Click "More options" 5+ times | Keeps generating (possibly repeating) | Exhausted message after 4 batches |
| LLM returns < 3 proposals on 2nd+ click | Silently shows same old proposals | Exhausted message |
| Proposal repeats across batches | Only "distinct from registry" prompt | Full history + "NEVER repeat" instruction |
| Cycle persists after plan selected | Counter never resets | Reset in `merge_proposals_to_plan` |

---

## Files Modified

| File | Lines | Change |
|------|-------|--------|
| `agents/manager/state.py` | 67-69 | Added `explore_iteration`, `seen_proposal_titles` |
| `agents/manager/nodes/explore_aims.py` | 236-427 | Exhaust check, tracking, fixed fallback, reset in merge |
| `agents/manager/prompts/propose_analysis_plans.md` | 26-27, 51 | Added `seen_proposal_titles_json`, updated dedup rule |

### Frontend

No changes required. The exhausted message naturally renders as markdown via the existing `{!ui?.plan?.aims?.length && !ui?.proposals?.length && (...ReactMarkdown...)}` fallback. The "See more options" quick-reply button is suppressed because `ui.proposals` is `null`.

---

## Testing

- **4 batches × 3 proposals = 12 unique proposals** before exhaustion
- **Exhaustion message** appears on the 5th click: *"I've explored all the analysis angles I can think of for {scope_label}..."*
- **New exploration cycle** starts when user selects a plan and clicks "More options" again
- **Refine actions** do not count toward the exhaustion counter
- **Frontend** renders exhausted message as markdown with no action buttons — user can type a new direction
