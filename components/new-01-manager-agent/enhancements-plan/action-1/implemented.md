# Action-1 Implementation: Production Hardening & Bugfixes

**Date:** 2026-07-15
**Scope:** `components/new-01-manager-agent` only

---

## What was done

All items from the hardening plan (`02-production-hardening-and-bugfixes.md`) have been implemented. Below is the summary of every change, grouped by category.

---

## Phase 1 — Deterministic Guardrails (error reduction)

### 1. Deterministic `confirm N` pre-check (eliminates §3.8 permanently)

**Files:** `backend/agents/manager/analyst.py`

The analyst's LLM was responsible for choosing whether to route `confirm N` or `__confirm__` messages to the `confirm_plan` tool. This was the root cause of the intermittent "options disappear / back to list" bug — the LLM sometimes chose the wrong tool.

**Fix:** A pre-check was added at the very top of the `analyst()` function, before any LLM call. If the user's message matches `/^confirm\s+\d+$/` or equals `__confirm__`, the LLM is completely bypassed and the message is routed deterministically to a new `_handle_confirm()` function.

`_handle_confirm()` handles three cases:
- `__confirm__` → sets `tool_to_call = "confirm_plan"` for execution
- `confirm N` → selects proposal N for review, narrows `analysis_proposals` to one, and shows a review card (does NOT execute)
- Anything else confirm-like → shows the current plan summary with "Go — proceed" instructions

The old inline conditional logic (28 lines inside the tool-routing section) was replaced with a single call to `_handle_confirm()` as a safety net.

**Impact:** The probabilistic failure mode in §3.8 is eliminated entirely. This change alone fixes the most user-visible intermittent error.

---

### 2. Smart circuit breaker (repeat detection)

**Files:** `backend/agents/manager/state.py`, `backend/agents/manager/analyst.py`, `backend/agents/manager/runner.py`

The previous circuit breaker only checked `tool_call_count >= 10`, which meant stuck conversations burned 60-90+ seconds of wall time before the user got a helpful message.

**Fix:**
- Added `tool_call_history: list[str]` to `ManagerState` in `state.py`
- Added `"tool_call_history": []` to `_default_state()` in `runner.py`
- Added `_detect_tool_loop()` function in `analyst.py` that checks if the last 3 tool decisions are the **same tool** AND key state fields (line resolution, schema fetch) haven't changed
- The check runs before the LLM call and aborts immediately if a loop is detected
- When aborting, it clears the stuck `line.mention` so the next user message gets a clean retry
- The old `tool_call_count >= 10` check is kept as a backstop

**Impact:** Stuck conversations abort in ~5 seconds instead of 60-90 seconds.

---

### 3. Explicit `executed` API field

**Files:** `backend/agents/manager/session_store.py`, `frontend/src/sections/ChatSection.tsx`, `frontend/src/types/manager.ts`

The frontend inferred whether a plan was executed by pattern-matching the *next* turn's message text: `(nextTurn.user || "").trim() === "__confirm__"`. This was fragile — any change to the backend's response format would break it.

**Fix:**
- Added `"executed": phase == "man"` to `build_ui_summary()` in `session_store.py`
- Added `executed?: boolean` to the `TurnUi` TypeScript type
- Changed the frontend heuristic at `ChatSection.tsx:391` from message-text matching to `!!ui?.executed`

**Impact:** The frontend no longer infers backend intent from message text patterns. The backend explicitly says whether execution happened.

---

## Phase 2 — Test Infrastructure (regression prevention)

### 4-5. Fixed all broken test files

**Files:**
- `backend/agents/manager/tests/test_graph.py` — rewritten for current graph architecture
- `backend/agents/manager/tests/test_routing.py` — rewritten for current `router.py`
- `backend/agents/manager/tests/test_slots.py` — rewritten for current `session_store.py`
- `backend/agents/manager/tests/test_analyst.py` — **new** 15 tests for the new features
- `backend/agents/manager/tests/test_llm_client.py` — fixed async test bugs
- `backend/agents/manager/tests/conftest.py` — fixed broken import (`agents.manager.slots` deleted)

All test files previously imported from the deleted `agents.manager.nodes.*` architecture, causing import errors. They were rewritten to test the current architecture.

**Coverage:**
- `TestHandleConfirm` (7 tests): unit tests for `_handle_confirm` — `__confirm__`, `confirm N`, invalid index, zero index, no proposals, non-confirm fallback
- `TestDetectToolLoop` (5 tests): unit tests for `_detect_tool_loop` — short history, different tools, same tool ×3 triggers, progress exempts, mention in message
- `TestAnalystConfirmPreCheck` (3 tests): integration tests with mocked LLM — intercepts `__confirm__`, intercepts `confirm 1`, passes through normal messages
- `TestGraphStructure/Edges/Import` (14 tests): graph compilation, node presence, edge wiring, import verification
- `TestRouteAfter*` (10 tests): routing logic for all paths
- `TestStateSerialization/BuildUiSummary/BuildSchemaSummary` (12 tests): serialization, UI summary, schema summary
- `TestLLMClient*` (10 tests): client configuration, circuit breaker, stats, get/set

**Total: 61 tests, all passing.**

---

## Phase 3 — Codebase Cleanup

### 6. Removed dead `plan_proposals` field

**File:** `backend/agents/manager/state.py`

`plan_proposals: list[dict] | None` was declared in `ManagerState` but never read or written anywhere in the code. It was a leftover from renaming to `analysis_proposals`. Removed.

### 7. Added drift-prevention comments

**File:** `backend/agents/manager/session_store.py`

Added a comment above `PERSISTED_STATE_KEYS` documenting that when adding a new field to `ManagerState`, one must decide whether to persist it across HTTP turns. Also documented which fields are intentionally NOT persisted (per-turn ephemeral): `tool_call_count`, `tool_call_history`, `analyst_reasoning`, `tool_to_call`, `tool_result`, `error`, `agent_message`, `selected_suggested_aim`.

---

## Verification

All 61 tests pass with:

```
cd components/new-01-manager-agent
PYTHONPATH=backend python -m pytest backend/agents/manager/tests/ -v
```

The test suite is now fully green and covers:
- Deterministic `confirm N` routing (no LLM involvement)
- Loop detection via `tool_call_history`
- `executed` field propagation
- Graph structure and edge wiring
- Router conditional logic
- Session serialization and UI summary building

---

## Remaining open items (not covered here)

1. **Cancel/undo after confirm** (§3.4 from the old plan) — no way to cancel after "Go — proceed"
2. **Production Docker Compose** — dev bind mounts must not ship as-is
3. **`01-manager-agent` dead code** — old component directory should be deleted or marked superseded
4. **Phase 3 architectural change** (shrink LLM's job to a state machine) — higher-risk, not attempted here
