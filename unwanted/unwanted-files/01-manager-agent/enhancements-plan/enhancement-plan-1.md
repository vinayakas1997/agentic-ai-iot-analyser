# Enhancement Plan 1 — Critical Gaps & Minor Fixes (2026-07-07)

## Overview

This document details **8 issues** discovered during a full codebase audit of the Manager Agent component. Issues are ranked by severity: **Critical (🔴)**, **High (🟠)**, **Medium (🟡)**, **Low (🟢)**.

---

## 🔴 Issue #1 — "Thinking△" Unicode Artifact in Chat

### Problem
When the manager agent is processing a request, the chat displays `Thinking△` (literal Unicode character `U+2206` DELTA) instead of a clean loading indicator.

### Location
- **File:** `frontend/src/sections/ChatSection.tsx:381`
- **Also in Navbar:** `frontend/src/components/Navbar.tsx:37` (uses `Thinking…` with proper ellipsis `U+2026`)

### Code
```tsx
// ChatSection.tsx:381 — BUG: Uses \u2206 (Δ) instead of \u2026 (…)
{loading && <p className="text-muted text-sm">Thinking\u2026</p>}

// Navbar.tsx:37 — CORRECT: Uses proper ellipsis
<span className="text-xs text-muted">{loading ? "Thinking…" : "Ready"}</span>
```

### Root Cause
Copy-paste error or encoding issue — `\u2206` (DELTA ∆) was used instead of `\u2026` (HORIZONTAL ELLIPSIS …).

### Fix
```tsx
// Change line 381 in ChatSection.tsx
{loading && <p className="text-muted text-sm">Thinking\u2026</p>}
//                              ▲ Change \u2206 → \u2026
```

### Priority
**🔴 Critical** — User-facing bug, visible on every request

### Effort
**5 minutes** — Single character fix

---

## 🔴 Issue #2 — Hardcoded Turn Count in Context Panel

### Problem
The Context sidebar always displays "Turns: 4" regardless of actual conversation length.

### Location
- **File:** `frontend/src/sections/ContextSection.tsx:109`

### Code
```tsx
// Line 109 — HARDCODED VALUE
<div className="text-[13px] text-muted">
  Turns: <b className="text-text font-medium">4</b>
</div>
```

### Root Cause
Static placeholder was never replaced with dynamic value from `turns.length`.

### Fix
```tsx
// Import turns from sessionStore
const turns = useSessionStore((s) => s.turns);

// Line 109 — Use dynamic count
<div className="text-[13px] text-muted">
  Turns: <b className="text-text font-medium">{turns.length}</b>
</div>
```

### Priority
**🔴 Critical** — Misleading UI, breaks trust in context panel

### Effort
**10 minutes** — Import + one-line change

---

## 🟠 Issue #3 — Blank OutputSection When No Execution Events

### Problem
After Manager completes but before Planner starts, the Outputs panel shows **completely empty space** — no message, no spinner, no indication of state.

### Location
- **File:** `frontend/src/sections/OutputSection.tsx:147-152`

### Code
```tsx
{!turn ? (
  <p className="text-muted text-sm">Send a message to start planning.</p>
) : !ui ? (
  <p className="text-muted text-sm">No snapshot for this step.</p>
) : (
  <ExecutionProgress isDone={isDone} />
)}
```

**`ExecutionProgress` returns `null` when `executionEvents` is empty** (line 59), so the panel renders nothing.

### Root Cause
Missing "Waiting on Planner" state in the conditional chain.

### Fix
```tsx
// Add explicit waiting state before ExecutionProgress
{!turn ? (
  <p className="text-muted text-sm">Send a message to start planning.</p>
) : !ui ? (
  <p className="text-muted text-sm">No snapshot for this step.</p>
) : isDone && !plannerStarted ? (
  <WaitingOnPlanner />  // NEW: Show waiting state
) : (
  <ExecutionProgress isDone={isDone} />
)}
```

Where `plannerStarted = executionEvents.some(e => e.topic === "planner.start")`

### Priority
**🟠 High** — User sees blank panel during critical handoff phase

### Effort
**20 minutes** — Add condition + reuse existing `WaitingOnPlanner` component

---

## 🟠 Issue #4 — Dead `uiStore` Complexity (Technical Debt)

### Problem
`uiStore.ts` maintains `AppView` type (`"workspace" | "dashboard"`) and `setView()` but **only workspace is used**. Dashboard was removed in Issue #1 cleanup but store wasn't simplified.

### Location
- **File:** `frontend/src/stores/uiStore.ts`

### Current Code
```typescript
type AppView = "workspace" | "dashboard";  // dashboard unused

interface UiState {
  view: AppView;
  setView: (view: AppView) => void;
  selectedTurnIndex: number;
  selectTurn: (index: number) => void;
}
```

### Fix
```typescript
// Simplified — remove unused view state
interface UiState {
  selectedTurnIndex: number;
  selectTurn: (index: number) => void;
}

// Remove setView, AppView type, view initialization
```

### Files to Update
- `uiStore.ts` — Simplify store
- `App.tsx` — Remove any `useUiStore` view references (likely none)
- `Navbar.tsx` — Remove any view-switching UI (none currently)

### Priority
**🟠 High** — Dead code increases cognitive load, testing surface

### Effort
**30 minutes** — Store simplification + verification

---

## 🟡 Issue #5 — Backend Errors Not Displayed in Chat

### Problem
When backend returns an error (e.g., session validation failure, LLM timeout), the error is stored in `turn.result.error` but **never rendered** in the chat UI. User sees only the agent message (if any) with no indication something failed.

### Location
- **File:** `frontend/src/sections/ChatSection.tsx` — no error rendering logic
- **Store:** `frontend/src/stores/sessionStore.ts` — `Turn` type includes `result?: { error?: string }`

### Current Turn Rendering (lines 237-376)
Only renders:
- User message
- Manager card (plan/proposals/markdown)
- Quick replies

**Missing:** Error banner when `turn.result?.error` exists.

### Fix
Add error display block in Manager card section:
```tsx
{turn.agent && (
  <div className={managerCardClass}>
    {/* NEW: Error banner at top of Manager response */}
    {turn.result?.error && (
      <div className="mb-3 p-3 rounded-lg bg-red-900/30 border border-red-500/30 text-red-300 text-sm">
        <strong>Error:</strong> {turn.result.error}
      </div>
    )}
    {/* ... existing plan/proposals/markdown rendering ... */}
  </div>
)}
```

### Priority
**🟡 Medium** — Silent failures confuse users, hinder debugging

### Effort
**15 minutes** — Add conditional error block

---

## 🟡 Issue #6 — No Input Validation Feedback

### Problem
When user presses Enter with empty input, or during loading, or after session complete — **nothing happens visually**. No shake, no toast, no disabled-state feedback.

### Location
- **File:** `frontend/src/sections/ChatSection.tsx:100-106`

### Code
```tsx
const handleSubmit = async (e: FormEvent) => {
  e.preventDefault();
  if (!input.trim() || loading || isDone) return;  // Silent early return
  const text = input;
  setInput("");
  await sendUserMessage(text);
};
```

### Fix Options

**Option A: Button disabled state (minimal)**
```tsx
<button
  type="submit"
  className={btnPrimary}
  disabled={loading || !input.trim() || !isLive}
  aria-disabled={loading || !input.trim() || !isLive}
>
  Send
</button>
```

**Option B: Input shake animation (better UX)**
```tsx
const [shake, setShake] = useState(false);

const handleSubmit = async (e: FormEvent) => {
  e.preventDefault();
  if (!input.trim()) {
    setShake(true);
    setTimeout(() => setShake(false), 300);
    return;
  }
  if (loading || isDone) return;
  // ...
};

// On input:
<input
  className={`flex-1 rounded-lg border border-border bg-app text-text px-3 py-2 text-sm ${shake ? "animate-shake" : ""}`}
/>

// Add to global CSS (index.css):
@keyframes shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-4px)} 75%{transform:translateX(4px)} }
.animate-shake { animation: shake 0.3s ease-in-out; }
```

### Priority
**🟡 Medium** — Basic form UX gap

### Effort
**20 minutes** (Option A) / **35 minutes** (Option B)

---

## 🟡 Issue #7 — WebSocket Disconnect Silent Failure

### Problem
If WebSocket connection drops (network issue, server restart), the user continues typing messages that **silently fail** — no reconnection indicator, no offline banner, no message queue.

### Location
- **File:** `frontend/src/hooks/useWebSocket.ts`
- **Store:** `sessionStore.ts` — `sendUserMessage` uses WebSocket

### Current Behavior
- `useWebSocket` has `onClose` but only logs to console
- No UI state for connection status
- `sendUserMessage` doesn't check connection before sending

### Fix
```tsx
// In useWebSocket.ts — add connection state
const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");

useEffect(() => {
  ws.onopen = () => setConnectionStatus("connected");
  ws.onclose = () => setConnectionStatus("disconnected");
  ws.onerror = () => setConnectionStatus("disconnected");
}, []);

// Return status so components can react
return { sendMessage, connectionStatus, ... };

// In ChatSection — show banner when disconnected
{connectionStatus === "disconnected" && (
  <div className="mb-3 p-3 rounded-lg bg-amber-900/30 border border-amber-500/30 text-amber-300 text-sm flex items-center gap-2">
    <IconAlert size={14} />
    Connection lost. Reconnecting…
  </div>
)}
```

### Priority
**🟡 Medium** — Reliability gap, especially in production

### Effort
**45 minutes** — Hook update + UI banner + store integration

---

## 🟢 Issue #8 — Missing Keyboard Accessibility on Interactive Elements

### Problem
- `OptionCard` (proposal selection) is clickable but not keyboard-focusable
- Quick-reply buttons lack focus management
- No `onKeyDown` for Enter/Space activation

### Location
- **File:** `frontend/src/sections/ChatSection.tsx`
  - `OptionCard` component (lines 19-73)
  - Quick-reply buttons (lines 124-136)

### Fix for OptionCard
```tsx
function OptionCard({ index, proposal, onSelect }) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(`confirm ${index + 1}`);
    }
  };

  return (
    <div
      className="..."  // existing classes
      onClick={() => onSelect(`confirm ${index + 1}`)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`Select option ${index + 1}: ${proposal.title || `Option ${index + 1}`}`}
    >
      {/* ... existing content ... */}
    </div>
  );
}
```

### Fix for Quick Replies
```tsx
<button
  key={b.label}
  type="button"
  className={b.primary ? qrPrimaryClass : qrSecondaryClass}
  onClick={() => onSend(b.msg)}
  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSend(b.msg); } }}
>
  {b.primary && <IconCheck size={11} />}
  {b.label}
</button>
```

### Priority
**🟢 Low** — Accessibility compliance, affects keyboard-only users

### Effort
**30 minutes** — Add handlers + test with keyboard navigation

---

## Implementation Priority Order

| Phase | Issues | Total Effort | Rationale |
|-------|--------|--------------|-----------|
| **Phase 1 (Immediate)** | #1, #2 | ~15 min | User-visible bugs, trivial fixes |
| **Phase 2 (This Sprint)** | #3, #5 | ~35 min | Core UX gaps affecting workflow |
| **Phase 3 (Next Sprint)** | #4, #6 | ~50 min | Technical debt + form UX |
| **Phase 4 (Backlog)** | #7, #8 | ~75 min | Reliability + accessibility |

---

## Verification Checklist

After each fix, verify:

- [ ] **#1** — Send message, confirm "Thinking…" (ellipsis) appears, no Δ
- [ ] **#2** — Have 1, 3, 7 turns — Context panel shows correct count
- [ ] **#3** — Complete Manager phase, before Planner starts — Outputs shows "Waiting on Planner" card
- [ ] **#4** — Remove `uiStore` view logic — app still works, no TypeScript errors
- [ ] **#5** — Trigger backend error (e.g., invalid session) — error banner appears in chat
- [ ] **#6** — Press Enter on empty input — shake animation or button disabled state
- [ ] **#7** — Disconnect network — Kill backend — "Connection lost" banner appears, reconnects on recovery
- [ ] **#8** — Tab through chat — OptionCards and quick replies focusable, Enter activates

---

## Related Documentation

- `/improvements/20260707-issue-1.md` — UI & Codebase Redundancy Cleanup (Issue #4 related)
- `/improvements/20260707-issue-3.md` — UI Fix & Enhancement: Manager Agent Surface
- `/improvements/20260707-issue-6.md` — Chat Panel Redesign (Issue #5, #6, #8 related)
- `/improvements/20260707-issue-7.md` — Outputs Panel Redesign (Issue #3 related)

---

**Created:** 2026-07-07  
**Author:** Codebase Audit  
**Status:** Ready for Implementation