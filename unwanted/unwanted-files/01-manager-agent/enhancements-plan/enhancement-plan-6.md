# Enhancement Plan 6 — Replace "Change Something" Button with Inline Input + Human-Readable Explanation (2026-07-09)

## Overview

Replace the generic "Change something..." button with an inline input box, and add a human-readable explanation message at the top of the manager card so the next turn acknowledges what the user asked for.

---

## Current Behavior

### The "Change something..." button

1. User clicks "Change something..." → sends generic `"change something"` message to backend
2. Backend responds with a plan that needs editing
3. User must then type their modifications in the main chat composer (separate location)

### The missing explanation

When proposals or a plan are shown, the `agent_message` text (`turn.agent`) is **hidden** — only structured UI (proposal cards / plan details) renders. This means:

- After user types "focus on suppliers", the response shows proposals but **does not acknowledge what the user asked**
- The turn feels robotic — no conversational thread

---

## Proposed Changes

### Change 1 — Inline input in quick-reply area

| Before | After |
|--------|-------|
| `[Change something...]` button sending generic `"change something"` | Button toggles an inline `<input>` + `[Apply]` / `[Cancel]` directly in the card |

Pressing **Enter** or **Apply** sends the typed text as a user message. **Escape** or **Cancel** hides the input without sending.

### Change 2 — `explanation` field in `TurnUi`

Add a new optional `explanation: string` field to the `TurnUi` type. When present, it renders at the top of the manager card (before the plan/proposals content) as a conversational intro.

### Change 3 — Backend populates `explanation`

| Node | Explanation text |
|------|-----------------|
| `propose_or_refine_plans` | `"You asked me to **{change_notes}**. Here are some updated options:"` (if change_notes exists) |
| `build_plan_message` | `"Here's the analysis plan for **{line_name}**:"` |

---

## Files to Modify

| File | Change |
|------|--------|
| `frontend/src/types/manager.ts` | Add `explanation?: string` to `TurnUi` |
| `frontend/src/sections/ChatSection.tsx` | Add `showChangeInput`/`changeInput` state; inline input in `buildQuickReplies`; render `explanation` at top of manager card |
| `backend/agents/manager/session_store.py` | Map `state["explanation"]` → `ui.explanation` in `build_ui_summary` |
| `backend/agents/manager/nodes/explore_aims.py` | Set `"explanation"` in `propose_or_refine_plans` return (uses `aim_exploration.change_notes`) |
| `backend/agents/manager/nodes/plan.py` | Set `"explanation"` in `build_plan_message` return |

---

## Behavior After Fix

```
User clicks "Change something..." → button replaced by inline input
User types "focus on suppliers" → presses Enter

Next turn:
┌─ Manager Card ──────────────────────────────┐
│  "You asked me to focus on suppliers.        │  ← new explanation
│   Here are some updated options:"            │
│                                             │
│  Option 1: Supplier Quality Analysis        │
│  Option 2: ...                              │
│                                             │
│  [See more options]  [Change something...]  │  ← ready for next change
└─────────────────────────────────────────────┘
```

---

## Verification Checklist

- [ ] Click "Change something..." shows inline input (not generic message)
- [ ] Pressing Enter sends the typed text
- [ ] Pressing Escape cancels and hides input
- [ ] Cancel button hides input without sending
- [ ] Apply button sends message when input is non-empty
- [ ] Input clears after successful send
- [ ] Input state resets when pending turn resolves
- [ ] `explanation` renders at top of manager card when proposals are shown
- [ ] `explanation` renders at top of manager card when plan is shown
- [ ] `propose_or_refine_plans` sets explanation with change_notes context
- [ ] `build_plan_message` sets explanation with line name
- [ ] Fallback: proposals without explanation show no extra text (card is self-explanatory)
- [ ] No regression on existing quick-reply buttons (Go, More options)
- [ ] TypeScript compiles with no errors
- [ ] Python compiles with no syntax errors
- [ ] Vite build succeeds
