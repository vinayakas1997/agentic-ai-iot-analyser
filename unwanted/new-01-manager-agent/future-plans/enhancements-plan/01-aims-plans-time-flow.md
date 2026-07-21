# Manager Agent Enhancement Plan: Aims, Plans, and Time Flow

**Session reference:** `00a148b-8f4a-4466-8289-7164e517a566`
**Query example:** "tell me about the japan_fruit"
**Date:** 2026-07-14

---

## Table of Contents

1. [Current Flow Summary](#1-current-flow-summary)
2. [Core Changes (Aims, Plans, Time)](#2-core-changes-aims-plans-time)
   - 2.1 Color-Coded Suggested Aims with Business KPI Values
   - 2.2 Scenario 1: User Selects from Suggested Aims
   - 2.3 Scenario 2: User Provides Custom Aim — Feasibility Assessment
   - 2.4 Time Default Notification
3. [Additional Issues Found](#3-additional-issues-found)
   - 3.1 "confirm 1" vs "__confirm__" Mismatch
   - 3.2 "more options" Doesn't Generate New Proposals
   - 3.3 Duplicate `_build_planner_schema_payload`
   - 3.4 No Cancel/Undo After Confirm
   - 3.5 `tool_call_count` Hard Stop
   - 3.6 No Feedback Loop for Failed Custom Aims
   - 3.7 `explore_phase` State Never Reset
   - 3.8 TypeScript Type Mismatch for `suggested_aims`
   - 3.9 `data_earliest_ts` Not Exposed to Frontend
   - 3.10 Cross-Dataset Aims Missing Join Context
   - 3.11 Advisory Word Limit Too Tight
   - 3.12 No Granular Loading State
   - 3.13 `seen_proposal_titles` Missing from Persisted Keys
4. [Files to Modify](#4-files-to-modify)
5. [Implementation Order](#5-implementation-order)

---

## 1. Current Flow Summary

### Query → Response Flow

```
User: "tell me about japan_fruit"
  ↓
inject_reference_time → analyst (LLM decides next step)
  ↓ calls extract_slots
Extract line mention "japan_fruit"
  ↓ calls resolve_line
Resolve "japan_fruit" → canonical JAPAN_SCENARIOS
  ↓ calls fetch_schema
Fetch 3 datasets (primary, secondary, tertiary)
  → Collects 12 suggested_aims (4 per dataset) into a flat list
  ↓ calls answer_advisory
LLM generates response mentioning all 12 aims
  ↓
Frontend shows 12 clickable suggestion buttons (no grouping, no color, no business value)
```

### Aim Selection → Plan Generation

```
User clicks suggestion (e.g., "total sales by prefecture")
  ↓
extract_slots (extracts aim_raw)
  ↓
reorganize_aims (refines aim into structured format)
  ↓
generate_plans (creates 3 proposals, possibly diverging from selected aim)
  ↓
User selects a proposal → confirm_plan → Planner runs queries
```

### Issue: No time specified

When user doesn't mention time, `resolve_time` sets `no_filter=True` and `confirm_plan` sends `time_range: null`. User is never told about this default behavior.

---

## 2. Core Changes (Aims, Plans, Time)

### 2.1 Color-Coded Suggested Aims with Business KPI Values

**Problem:** 12 flat aims with no grouping, no dataset association, no business value explanation.

**Solution:**

#### Backend: `backend/agents/manager/tools/fetch_schema.py` (lines 67-70)

Change the flat list comprehension to return structured objects:

```python
# Before:
"suggested_aims": [
    aim for ds in datasets
    for aim in (ds.get("suggested_aims") or [])
],

# After:
"suggested_aims": [
    {
        "aim": aim,
        "dataset": ds.get("dataset_name"),
        "role": ds.get("role"),
        "kpi_value": "",  # populated by LLM in advisory_answer prompt
    }
    for ds in datasets
    for aim in (ds.get("suggested_aims") or [])
],
```

#### Backend: `backend/agents/manager/prompts/advisory_answer.md`

Add instruction to LLM to explain each aim's business KPI value in one sentence:

```markdown
For each suggested aim, include a short business KPI value explanation:
- What insight the user gains
- Why it matters for their business decisions
- Example: "total sales by prefecture → Identify which regions generate the most revenue and where marketing should focus."
```

#### Backend: `backend/agents/manager/session_store.py` (lines 286-305)

Update `build_ui_summary()` to pass the structured suggested_aims through to the UI.

#### Frontend: `frontend/src/sections/ChatSection.tsx` (lines 594-610)

Rewrite the suggested aims rendering to:

1. Group aims by dataset name with dataset header
2. Color-code the suggestion buttons by dataset role (primary=blue, secondary=amber, tertiary=coral)
3. Show KPI value text below each aim in muted text
4. Add a separator and note at the bottom:
   > "These are per-dataset suggestions. If you have complex or cross-relational analysis needs, share your thoughts and I'll create a custom plan."

#### Frontend: `frontend/src/types/manager.ts`

Update `TurnUi.suggested_aims` type:

```typescript
// Before:
suggested_aims?: string[];

// After:
suggested_aims?: {
    aim: string;
    dataset: string;
    role: string;
    kpi_value?: string;
}[];
```

#### Visual Layout Mockup:

```
┌─ japan_fruit_sales (Primary) ─────────────────────┐
│ [blue] total sales by prefecture               ← │
│   → Identifies top revenue regions for budget    │
│ [blue] average price per kg by fruit and season ← │
│   → Optimizes pricing strategy across seasons    │
│ [blue] festival season sales impact            ← │
│   → Measures ROI of festival participation       │
│ [blue] top selling fruits per region           ← │
│   → Informs regional inventory allocation        │
└──────────────────────────────────────────────────┘

┌─ japan_fruit_inventory (Secondary) ───────────────┐
│ [amber] stock levels by prefecture and fruit    ← │
│   → Prevents stockouts and overstock situations  │
│ [amber] supplier lead time analysis            ← │
│   → Identifies reliable suppliers, reduces risk  │
│ ...                                               │
└──────────────────────────────────────────────────┘

┌─ japan_supplier_quality (Tertiary) ───────────────┐
│ [coral] quality score trends by prefecture      ← │
│   → Tracks quality changes to identify issues    │
│ ...                                               │
└──────────────────────────────────────────────────┘

── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
These are per-dataset suggestions. For complex or
cross-relational analysis, share your thoughts and
I'll create a custom plan.
```

---

### 2.2 Scenario 1: User Selects from Suggested Aims

**Problem:** When user clicks a suggested aim, `generate_plans` creates 3 proposals that may diverge from the selected aim. Business value is not explained before the plan is shown.

**Solution:**

#### Backend: `backend/agents/manager/analyst.py`

Add detection logic (around lines 222-234): When user message exactly matches one of the suggested aim strings, set a flag to indicate this is a "suggested aim selection" path:

```python
# After existing has_aim guard, add:
suggested_aims = (state.get("line_context") or {}).get("suggested_aims") or []
selected_suggested = any(
    aim == user_message
    for s_aim in suggested_aims
    for aim in ([s_aim] if isinstance(s_aim, str) else [s_aim.get("aim")])
)
if selected_suggested:
    state["selected_suggested_aim"] = user_message
```

#### Backend: `backend/agents/manager/tools/generate_plans.py`

When `selected_suggested_aim` is set in state, generate **1 focused proposal** instead of 3:

```python
# After proposals normalization:
if state.get("selected_suggested_aim"):
    # Keep only the proposal matching the selected aim
    normalized = [p for p in normalized if state["selected_suggested_aim"] in p.get("aims", [])]
    if not normalized:
        # If no match, create one from the selected aim
        normalized = [{
            "id": 1,
            "title": state["selected_suggested_aim"],
            "aims": [state["selected_suggested_aim"]],
            "what_you_might_see": "This analysis focuses on " + state["selected_suggested_aim"],
        }]
```

#### Backend: `backend/agents/manager/prompts/propose_analysis_plans.md`

Add conditional instruction:

```markdown
When user selected a specific suggested aim (check user_message):
- Return exactly 1 proposal focused on that aim
- Include detailed business value explanation in what_you_might_see
- Do not add extra aims beyond what the user selected
```

#### Frontend: `frontend/src/sections/ChatSection.tsx`

When a single focused plan is returned (not 3 proposals), show:
- Business KPI value explanation prominently
- The plan aims
- "Go — proceed" button directly (skip the multi-choice step)

---

### 2.3 Scenario 2: User Provides Custom Aim — Feasibility Assessment

**Problem:** When user provides a custom aim not from registry suggestions, the system blindly creates 3 proposals without checking if the aim is achievable with available data.

**Solution:**

#### Backend: `backend/agents/manager/tools/generate_plans.py`

Add feasibility assessment logic. The LLM prompt should instruct it to evaluate:

1. **Data availability**: Do the required columns/tables exist in the schema?
2. **Join feasibility**: Can the required datasets be joined?
3. **Time range impact**: Is the requested time range supported by the data?

Return structure:

```python
{
    "proposals": [
        {
            "id": 1,
            "title": "Custom analysis: ...",
            "aims": ["..."],
            "what_you_might_see": "...",
            "feasible": true/false,
            "feasibility_reason": "Available: sales.price, sales.quantity by prefecture. Missing: cost data. Suggest using revenue as proxy.",
            "alternative": "If not feasible, suggest closest alternative aim"
        }
    ]
}
```

#### Backend: `backend/agents/manager/prompts/propose_analysis_plans.md`

Add feasibility instruction:

```markdown
When user's aim is NOT from registry suggested aims:
1. First assess feasibility based on available columns, tables, and joins
2. Return `feasible: true/false`
3. In `feasibility_reason`, list which columns support the aim and which are missing
4. If not feasible, suggest a specific alternative aim in `alternative`
5. Always produce exactly 1 proposal for custom aims
```

#### Frontend: `frontend/src/sections/ChatSection.tsx`

Render feasibility indicator:

- Green badge: "Doable" + reason listing supporting columns
- Red badge: "Not doable" + reason + alternative suggestion
- Clickable alternative suggestion that the user can select

---

### 2.4 Time Default Notification

**Problem:** When user doesn't specify a time range, the system silently uses `no_filter=True`, which means all data. The user isn't told and can't adjust.

**Solution:**

#### Backend: `backend/agents/manager/tools/resolve_time.py` (lines 21-29)

When `no_filter` is set, look up `data_earliest` from `line_context` to show the default range:

```python
if not raw:
    # Find earliest data timestamp across all datasets
    datasets = (state.get("line_context") or {}).get("dataset_summaries") or []
    earliest = min(
        (ds.get("data_earliest_ts") for ds in datasets if ds.get("data_earliest_ts")),
        default=None
    )
    time_slot["resolved"] = True
    time_slot["no_filter"] = True
    time_slot["default_range"] = True
    time_slot["data_earliest"] = earliest
    slots["time"] = time_slot
    return {
        **state,
        "slots": slots,
        "tool_result": json.dumps({"status": "no_filter", "data_earliest": earliest}),
    }
```

#### Backend: `backend/agents/manager/session_store.py`

In `build_ui_summary()`, add a notice when `no_filter` is true:

```python
if time_slot.get("no_filter"):
    ui_summary["time_default_notice"] = (
        "No time range specified — using all available data "
        f"(from {time_slot.get('data_earliest') or 'earliest record'}). "
        "If you need a specific period, let me know and I'll adjust the plan."
    )
```

#### Backend: `backend/agents/manager/prompts/advisory_answer.md`

Add rule:

```markdown
- When `no_filter` is true (no time range specified), explicitly tell the user:
  "I'm using the full available data range. If you have a specific time period in mind, "
  "let me know and I'll update the plan accordingly."
```

#### Frontend: `frontend/src/sections/ChatSection.tsx`

When `ui.time_default_notice` is present, show a subtle info banner:

```tsx
{ui?.time_default_notice && (
    <div className="mt-2 p-2 rounded-lg bg-ic-blue-soft/30 border border-ic-blue/20 text-[12px] text-ic-blue">
        {ui.time_default_notice}
    </div>
)}
```

#### Frontend: `frontend/src/types/manager.ts`

Add field:

```typescript
time_default_notice?: string;
```

---

## 3. Additional Issues Found

### 3.1 "confirm 1" vs "__confirm__" Mismatch

**Bug | High priority**

**File:** `frontend/src/sections/ChatSection.tsx` line 40, `backend/agents/manager/analyst.py` line 253

**Details:**
- When user clicks an OptionCard, the frontend sends `"confirm 1"`, `"confirm 2"`, or `"confirm 3"` as the user message
- The analyst guard at `analyst.py:253` only checks for `user_message.strip() != "__confirm__"`
- Since `"confirm 1"` ≠ `"__confirm__"`, the guard triggers and shows "Press **Go — proceed** to confirm and execute" instead of actually confirming
- The LLM can sometimes route it through `answer_advisory`, but this is unreliable

**Fix:**
In `analyst.py`, add a handler for `"confirm {n}"` pattern:

```python
import re
confirm_match = re.match(r'^confirm\s+(\d+)$', user_message.strip().lower())
if confirm_match:
    # Select the proposal at index (n-1) and route to confirm_plan
    proposal_idx = int(confirm_match.group(1)) - 1
    proposals = state.get("analysis_proposals") or []
    if 0 <= proposal_idx < len(proposals):
        selected = proposals[proposal_idx]
        # Set plan from selected proposal
        state["plan"] = {
            "aims": selected.get("aims", []),
            "benefits": selected.get("what_you_might_see", ""),
        }
        result["tool_to_call"] = "confirm_plan"
        result["phase"] = "tool"
        return result
```

Alternatively, update the frontend to send `"__confirm__"` and handle it properly, but the cleaner fix is to handle `"confirm {n}"` in the backend.

---

### 3.2 "more options" Doesn't Generate New Proposals

**Bug | High priority**

**File:** `backend/agents/manager/prompts/analyst.md` rule 10, `backend/agents/manager/tools/answer_advisory.py`

**Details:**
- When user clicks "more options" (or types "more options"), the analyst prompt rule 10 routes it to `answer_advisory`
- `answer_advisory` is a general Q&A tool — it doesn't call `generate_plans` or create new proposals
- The user gets the same explanation again with no new options

**Fix:**
Route "more options" to `generate_plans` instead of `answer_advisory`:

In `analyst.py` or the `answer_advisory` tool itself, detect "more options" and re-call `generate_plans`:

```python
if "more options" in user_message.lower() or "another option" in user_message.lower():
    result["tool_to_call"] = "generate_plans"
    result["phase"] = "tool"
    return result
```

This requires `generate_plans` to understand it should generate different proposals than previously shown (the prompt already handles this via `seen_proposal_titles`).

---

### 3.3 Duplicate `_build_planner_schema_payload`

**Code Quality | Medium priority**

**Files:**
- `backend/agents/manager/session_store.py` lines 82-97
- `backend/agents/manager/tools/confirm_plan.py` lines 105-120

**Details:**
The exact same function `_build_planner_schema_payload` exists in both files with identical logic. Any change to one must be manually replicated in the other.

**Fix:**
Extract to a shared utility module, e.g. `backend/agents/manager/schema_utils.py`:

```python
# schema_utils.py
def build_planner_schema_payload(line_context: dict | None, dataset_context: dict | None) -> dict:
    # ... shared logic ...
```

Then import it in both files:

```python
from agents.manager.schema_utils import build_planner_schema_payload
```

---

### 3.4 No Cancel/Undo After Confirm

**UX Issue | Low priority**

**File:** `backend/agents/manager/tools/confirm_plan.py`, `frontend/src/sections/ChatSection.tsx` lines 718-759

**Details:**
- After `confirm_plan` runs, it publishes to `"planner.start"` event bus topic
- The planner picks it up asynchronously
- The frontend shows "Session complete" with actions: Edit (before planner starts), Fork, New
- If the user changes their mind during the brief window before the planner starts, there's no "Cancel" action
- The Edit button requires planner not to have started, but there's no way to know if it has

**Fix:**
Add a "Cancel plan" action that works during the initial window:

```python
# In confirm_plan.py, before publishing:
# Return a pending state instead of immediately publishing
# Let user confirm via a separate "execute" step

# Or add cancel support:
# - Store the plan as "pending" in the database
# - Add a cancel endpoint that removes pending plans
# - Auto-execute after timeout or on explicit second confirm
```

Also add a `cancelPlan` action in the frontend for confirmed-but-not-yet-executed plans.

---

### 3.5 `tool_call_count` Hard Stop

**Robustness | Medium priority**

**File:** `backend/agents/manager/analyst.py` lines 246-250

**Details:**
- At 10 tool calls, the system immediately stops with "I've gathered enough information"
- This is a silent failure — no attempt to produce partial results or proposals
- Long conversational flows (user refining aims multiple times) can hit this limit

**Fix:**
Instead of a hard stop, force `generate_plans` or `answer_advisory`:

```python
if tool_call_count >= 10:
    has_schema = session_json.get("schema_fetched")
    has_aim = bool(session_json.get("aim", {}).get("raw") or session_json.get("aim", {}).get("aims"))
    
    if has_schema and has_aim:
        result["tool_to_call"] = "generate_plans"  # Gracefully generate plans
    elif has_schema:
        result["tool_to_call"] = "answer_advisory"  # Summarize what we know
    else:
        result["agent_message"] = "I've gathered enough information. Let me summarize what I know and suggest next steps."
    
    result["phase"] = "tool" if result.get("tool_to_call") else "ask"
    return result
```

---

### 3.6 No Feedback Loop for Failed Custom Aims

**UX Issue | Low priority**

**File:** `backend/agents/manager/prompts/propose_analysis_plans.md`, `backend/agents/manager/tools/answer_advisory.py`

**Details:**
- When a custom aim is deemed not feasible, the system just shows the reason
- The user has no clear next step — they need to manually rephrase their aim
- The advisory ends with generic "pick an aim or confirm a plan" guidance

**Fix:**
When feasibility says not doable:
1. Show the alternative suggestion as a clickable option
2. Allow the user to accept, modify, or try something else
3. The advisory prompt should end with 2-3 specific suggestions instead of one generic sentence

In `frontend/src/sections/ChatSection.tsx`, add an inline suggestion that user can click:

```tsx
{feasible === false && alternative && (
    <button onClick={() => onSend(alternative)} className="...">
        Try: {alternative}
    </button>
)}
```

---

### 3.7 `explore_phase` State Never Reset

**State Management | Medium priority**

**File:** `backend/agents/manager/state.py` (field `explore_phase`), various tools

**Details:**
- `explore_phase` is set to `"proposing"` in `generate_plans` (line 97)
- It is never reset — even if the user changes topics or starts a new conversation within the same session
- This means the system may behave differently on subsequent turns (e.g., skipping proposal generation because it "already proposed")

**Fix:**
Reset `explore_phase` when:
1. The user provides a new line mention different from the current one
2. The user explicitly asks for a new/different analysis
3. After plan confirmation (set to `None`)

In `analyst.py`, add a reset check:

```python
# When extracting slots, if line mention changes, reset explore_phase
if session_json.get("line", {}).get("mention") and not session_json.get("line", {}).get("resolved"):
    state["explore_phase"] = None
```

---

### 3.8 TypeScript Type Mismatch for `suggested_aims`

**Bug (if not fixed) | High priority**

**File:** `frontend/src/types/manager.ts` lines 1-33, `frontend/src/sections/ChatSection.tsx` lines 594-610

**Details:**
- Currently typed as `suggested_aims?: string[]`
- After our core change (2.1), the backend will return `{ aim, dataset, role, kpi_value }[]`
- The frontend will access `aim` property on what it thinks is a string, resulting in runtime errors or blank rendering

**Fix:**
Update the type definition:

```typescript
suggested_aims?: {
    aim: string;
    dataset: string;
    role: string;
    kpi_value?: string;
}[];
```

And update all consumer code that iterates over `suggested_aims` to use the new shape.

---

### 3.9 `data_earliest_ts` Not Exposed to Frontend

**Missing Feature | Medium priority**

**File:** `backend/agents/manager/session_store.py` lines 137-203, `frontend/src/types/manager.ts`

**Details:**
- `data_earliest_ts` exists in the backend's `dataset_summaries` object
- But `build_schema_summary()` at line 154 includes it per-dataset, not as a consolidated value
- The frontend has no way to display "Using all data from X to Y" without calculating it client-side

**Fix:**
In `build_schema_summary()`, add a consolidated `data_available_from` field:

```python
# After datasets loop:
earliest_list = [
    ds.get("data_earliest_ts") for ds in datasets_full
    if isinstance(ds, dict) and ds.get("data_earliest_ts")
]
data_available_from = min(earliest_list) if earliest_list else None

return {
    ...existing_fields,
    "data_available_from": data_available_from,
}
```

In `frontend/src/types/manager.ts`:
```typescript
data_available_from?: string | null;
```

---

### 3.10 Cross-Dataset Aims Missing Join Context

**UX Improvement | Low priority**

**File:** `frontend/src/sections/ChatSection.tsx`

**Details:**
- When showing suggested aims grouped by dataset, users may not know which datasets can be joined
- The join_catalog exists in the schema but isn't shown alongside the aims
- Users might ask for analysis that requires joins they don't know are possible

**Fix:**
Between grouped dataset sections, show a join hint when there are cross-dataset joins available:

```tsx
{joins.length > 0 && (
    <div className="text-[11px] text-ic-blue mt-1 mb-2">
        Cross-table analysis available: {joins.map(j => `${j.left_dataset} ↔ ${j.right_dataset}`).join(", ")}
    </div>
)}
```

This should appear below the grouped dataset sections, encouraging users to think about cross-relational analysis.

---

### 3.11 Advisory Word Limit Too Tight

**Content Issue | Low priority**

**File:** `backend/agents/manager/prompts/advisory_answer.md` line 38

**Details:**
- The prompt says "Keep the answer concise (under 200 words)"
- With 12 suggested aims each needing a KPI value explanation, 200 words is about 16 words per aim
- This is too short for meaningful business value explanations

**Fix:**
Increase the word limit to 350-400 words, or change to a structured format:

```markdown
- Keep the answer under 400 words
- For suggested aims, use a bullet list with brief KPI value (1 sentence each)
```

Alternatively, separate the advisory into two sections:
1. Brief text response (under 200 words)
2. Structured suggested_aims display (handled by frontend, not LLM)

---

### 3.12 No Granular Loading State

**UX Improvement | Low priority**

**File:** `frontend/src/stores/sessionStore.ts`, `frontend/src/sections/ChatSection.tsx`

**Details:**
- The frontend has a single `loading` boolean
- When loading is true, the input is disabled and a generic spinner shows
- User doesn't know what step is being processed (extracting, resolving, generating plans, etc.)

**Fix:**
Add a `statusMessage` field to the session store:

```typescript
// In sessionStore:
statusMessage: string | null;
setStatusMessage: (msg: string | null) => void;

// When sending a message:
set({ loading: true, statusMessage: "Analyzing your request..." });
```

Backend can optionally include a `status` field in responses, or the frontend can derive it from the phase:

```typescript
const phaseLabels: Record<string, string> = {
    extract: "Analyzing your request...",
    ask: "Processing...",
    tool: "Gathering data...",
    man: "Building analysis plan...",
};
```

---

### 3.13 `seen_proposal_titles` Missing from Persisted State Keys

**Bug | Medium priority**

**File:** `backend/agents/manager/session_store.py` lines 7-33

**Details:**
- `seen_proposal_titles` tracks which proposal titles have already been shown to the user
- `PERSISTED_STATE_KEYS` (lines 7-33) lists 23 keys that are saved to PostgreSQL
- `seen_proposal_titles` is NOT in this list
- If a session is resumed (e.g., user comes back to it later), the system won't know which proposals were already shown
- This means `generate_plans` may show duplicate proposals on resume

**Fix:**
Add `seen_proposal_titles` to `PERSISTED_STATE_KEYS`:

```python
# After "user_explore_intent",
"seen_proposal_titles",
```

Also check if any other state keys are missing:
- `seen_proposal_titles` — NOT persisted ❌ (needs fix)
- `analysis_proposals` — IS persisted ✓
- `explore_iteration` — NOT persisted (likely fine, regenerated)
- `session_intent` — NOT persisted (likely fine, regenerated)
- `user_explore_intent` — IS persisted ✓

---

## 4. Files to Modify

### Core Changes

| # | File | Change |
|---|------|--------|
| 2.1 | `backend/agents/manager/tools/fetch_schema.py` | Structure suggested_aims with dataset/role |
| 2.1 | `backend/agents/manager/prompts/advisory_answer.md` | Add KPI value instruction, increase word limit |
| 2.1 | `backend/agents/manager/session_store.py` | Pass structured suggested_aims to UI summary |
| 2.1 | `frontend/src/sections/ChatSection.tsx` | Grouped color-coded aims with KPI values + note |
| 2.1 | `frontend/src/types/manager.ts` | Update suggested_aims type |
| 2.2 | `backend/agents/manager/analyst.py` | Detect suggested aim selection flag |
| 2.2 | `backend/agents/manager/tools/generate_plans.py` | Single focused proposal for selected aim |
| 2.2 | `backend/agents/manager/prompts/propose_analysis_plans.md` | Conditional for single proposal |
| 2.3 | `backend/agents/manager/tools/generate_plans.py` | Feasibility assessment for custom aims |
| 2.3 | `backend/agents/manager/prompts/propose_analysis_plans.md` | Feasibility instruction |
| 2.4 | `backend/agents/manager/tools/resolve_time.py` | Default time range from data_earliest |
| 2.4 | `backend/agents/manager/session_store.py` | time_default_notice in UI summary |
| 2.4 | `backend/agents/manager/prompts/advisory_answer.md` | Explicit time default notification instruction |
| 2.4 | `frontend/src/types/manager.ts` | Add time_default_notice field |
| 2.4 | `frontend/src/sections/ChatSection.tsx` | Render time default notice |

### Additional Fixes

| # | File | Change |
|---|------|--------|
| 3.1 | `backend/agents/manager/analyst.py` | Handle "confirm {n}" pattern |
| 3.2 | `backend/agents/manager/analyst.py` | Route "more options" to generate_plans |
| 3.3 | **New:** `backend/agents/manager/schema_utils.py` | Extract shared function |
| 3.3 | `backend/agents/manager/session_store.py` | Use shared import |
| 3.3 | `backend/agents/manager/tools/confirm_plan.py` | Use shared import |
| 3.4 | `backend/agents/manager/tools/confirm_plan.py` | Add cancel window |
| 3.4 | `frontend/src/sections/ChatSection.tsx` | Add cancel action |
| 3.5 | `backend/agents/manager/analyst.py` | Graceful degradation at tool call limit |
| 3.6 | `backend/agents/manager/prompts/propose_analysis_plans.md` | Alternative suggestions |
| 3.6 | `frontend/src/sections/ChatSection.tsx` | Clickable alternative |
| 3.7 | `backend/agents/manager/analyst.py` | Reset explore_phase on new topic |
| 3.8 | `frontend/src/types/manager.ts` | Type fix for suggested_aims |
| 3.8 | `frontend/src/sections/ChatSection.tsx` | Consumer code update |
| 3.9 | `backend/agents/manager/session_store.py` | Add data_available_from |
| 3.9 | `frontend/src/types/manager.ts` | Add field |
| 3.10 | `frontend/src/sections/ChatSection.tsx` | Join hints between dataset groups |
| 3.11 | `backend/agents/manager/prompts/advisory_answer.md` | Increase word limit |
| 3.12 | `frontend/src/stores/sessionStore.ts` | Add statusMessage |
| 3.12 | `frontend/src/sections/ChatSection.tsx` | Show step status |
| 3.13 | `backend/agents/manager/session_store.py` | Add seen_proposal_titles to PERSISTED_STATE_KEYS |

---

## 5. Implementation Order

```
Phase 1 — Bug Fixes (High Priority)
├── 3.1  "confirm 1" vs "__confirm__" mismatch
├── 3.2  "more options" routing
├── 3.8  TypeScript type fix
└── 3.13 Add seen_proposal_titles to persisted keys

Phase 2 — Core Changes (Medium Priority)
├── 2.1  Color-coded aims with KPI values
├── 2.2  Scenario 1: Selected aim focused plan
├── 2.3  Scenario 2: Custom aim feasibility
└── 2.4  Time default notification

Phase 3 — Code Quality & UX (Medium Priority)
├── 3.3  Extract duplicate function
├── 3.5  Graceful tool_call_count degradation
├── 3.7  Reset explore_phase
├── 3.9  Expose data_earliest to frontend
└── 3.11 Increase word limit

Phase 4 — Polish (Low Priority)
├── 3.4  Cancel after confirm
├── 3.6  Feedback loop for failed aims
├── 3.10 Join context in UI
└── 3.12 Granular loading state
```
