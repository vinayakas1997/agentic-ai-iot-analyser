# Enhancement Plan 6 — Resolution Summary

All changes from `enhancement-plan-6.md` implemented.  
Verification: `python3 -m py_compile explore_aims.py` ✓, `python3 -m py_compile plan.py` ✓, `python3 -m py_compile session_store.py` ✓, `npx tsc --noEmit` ✓, `vite build` ✓.

---

## Change 1 — Inline Input in Quick-Reply Area

**File:** `frontend/src/sections/ChatSection.tsx:115-116, 117-123, 134-173`

### State variables added (lines ~115):

```typescript
const [showChangeInput, setShowChangeInput] = useState(false);
const [changeInput, setChangeInput] = useState("");
```

### Reset on pending turn resolve (lines ~118-124):

```typescript
useEffect(() => {
  if (!pendingTurn) {
    setActiveProposal(null);
    setShowChangeInput(false);
    setChangeInput("");
  }
}, [pendingTurn]);
```

### `buildQuickReplies` restructured (lines ~134-173):

The old "Change something..." button that pushed `{ label: "Change something…", msg: "change something" }` into the `btns` array is removed. Instead:

- **Normal state**: Renders a `<button>` with `IconEdit` that calls `setShowChangeInput(true)` on click
- **Input state**: Renders a `<div>` containing:
  - `<input type="text">` with Enter → send, Escape → cancel
  - `[Apply]` button → sends typed text via `onSend()`
  - `[Cancel]` button → hides input, clears text

The `showChange` flag controls visibility of this section entirely (hidden when `ui.proposals` and `ui.plan.aims` are both absent).

---

## Change 2 — `explanation` Field in `TurnUi`

**File:** `frontend/src/types/manager.ts:11`

```typescript
export interface TurnUi {
  ...
  explanation?: string;
}
```

---

## Change 3 — Frontend Renders Explanation

**File:** `frontend/src/sections/ChatSection.tsx:284-291`

New block inserted after the Manager header, before the plan/proposals modes:

```tsx
{ui?.explanation && (
  <div className="text-sm text-muted leading-relaxed mb-3 [&>p]:m-0">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>
      {ui.explanation}
    </ReactMarkdown>
  </div>
)}
```

Renders as a conversational intro above the structured card.

---

## Change 4 — Backend Maps `explanation`

**File:** `backend/agents/manager/session_store.py:250`

```python
"explanation": state.get("explanation"),
```

Added to the `build_ui_summary()` return dict.

---

## Change 5 — `propose_or_refine_plans` Sets Explanation

**File:** `backend/agents/manager/nodes/explore_aims.py:408-413`

Before the return block, the function reads `aim_exploration.change_notes`:

```python
change_notes = aim_exploration.get("change_notes", "")
explanation = (
    f"You asked me to **{change_notes}**. Here are some updated options:"
    if change_notes
    else None
)
```

Then included in the return dict alongside `agent_message`:

```python
return {
    **state,
    "analysis_proposals": proposals,
    ...
    "agent_message": format_proposals_message(proposals, scope_label),
    "explanation": explanation,
    ...
}
```

When there are no change_notes (e.g., first-time "More options"), explanation is `None` and nothing renders — the existing proposals intro text (`"Here are N options for..."`) already serves as context.

---

## Change 6 — `build_plan_message` Sets Explanation

**File:** `backend/agents/manager/nodes/plan.py:270-272`

```python
line_name = plan.get("line") or (slots.get("line") or {}).get("canonical") or "this line"
explanation = f"Here's the analysis plan for **{line_name}**:"
return {**state, "plan": plan, "agent_message": msg, "explanation": explanation, "phase": "plan"}
```

The `agent_message` (full structured plan text) is preserved unchanged for CLI/DB backward compatibility.

---

## Behavior Comparison

| Scenario | Before | After |
|---|---|---|
| Click "Change something..." | Sends generic `"change something"` to backend | Inline `<input>` appears in-card |
| Type modification | Must type in main composer (separate location) | Type directly next to the card |
| Submit modification | Extra round trip | Enter/Apply sends directly |
| Response after "focus on suppliers" | Shows proposals but no acknowledgment | Shows *"You asked me to focus on suppliers. Here are some updated options:"* |
| Response after selecting a plan | Shows plan card with no intro | Shows *"Here's the analysis plan for Vinayaka:"* |
| First-time "More options" | Proposals intro from `agent_message` hidden | Card shows proposals with no redundant intro (explanation is `None`) |
| Cancel | N/A | Escape or Cancel button hides input |

---

## Example Flow

```
Turn N:
┌─ Manager Card ──────────────────────────────┐
│  Plan: Analyze Vinayaka defects             │
│  Aims: root_cause, trend_analysis           │
│                                             │
│  [Go — proceed] [More options]              │
│  [Change something...]                      │
└─────────────────────────────────────────────┘

User clicks "Change something...":
┌─ Manager Card ──────────────────────────────┐
│  Plan: Analyze Vinayaka defects             │
│  Aims: root_cause, trend_analysis           │
│                                             │
│  [Go — proceed] [More options]              │
│  [input: "focus on suppliers"] [Apply] [X]  │
└─────────────────────────────────────────────┘

User presses Enter:

Turn N+1:
┌─ Manager Card ──────────────────────────────┐
│  You asked me to focus on suppliers.         │  ← explanation
│  Here are some updated options:              │
│                                             │
│  Option 1: Supplier Quality Deep Dive       │
│  Option 2: Lead Time Analysis               │
│                                             │
│  [See more options]  [Change something...]  │
└─────────────────────────────────────────────┘
```

---

## Files Modified

| File | Lines | Change |
|------|-------|--------|
| `frontend/src/types/manager.ts` | 11 | Added `explanation?: string` to `TurnUi` |
| `frontend/src/sections/ChatSection.tsx` | 115-116, 118-124, 134-173, 284-291 | State, inline input, explanation render |
| `backend/agents/manager/session_store.py` | 250 | Map `explanation` in `build_ui_summary` |
| `backend/agents/manager/nodes/explore_aims.py` | 408-413, 421 | Set `explanation` from `change_notes` |
| `backend/agents/manager/nodes/plan.py` | 270-272 | Set `explanation` with line name |

---

## Testing

- **Inline input**: Click → input appears → type → Enter sends → input clears → input resets when turn resolves
- **Escape/Cancel**: Closes input without sending, clears text
- **Explanation for proposals**: *"You asked me to {change_notes}. Here are some updated options:"* renders above proposals
- **Explanation for plan**: *"Here's the analysis plan for {line_name}:"* renders above plan card
- **No explanation for first-time proposals**: `explanation` is `None`, no redundant text shown
- **Backward compat**: `agent_message` unchanged for CLI/DB; existing sessions without `explanation` render normally (no text above card)
- **Quick replies**: Go, More options, See more options buttons unaffected
