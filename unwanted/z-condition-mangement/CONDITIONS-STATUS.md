# Condition Management — Status Tracker

> Auto-updated as each condition is discussed, designed, and resolved.
> This file tracks all scenarios for the "Auto-generate SQL when AIM is attached" feature.

## Status Key

| Status | Meaning |
|---|---|
| 🔴 NOT HANDLED | Not yet discussed or designed |
| 🟡 IN DISCUSSION | Being discussed with user |
| 🟢 DESIGNED | Solution designed, ready for implementation |
| ✅ RESOLVED | Implemented and verified |
| ❌ BLOCKED | Blocked by another condition or external factor |

## Conditions Status Table

| # | Condition | Status | Resolution | Notes |
|---|---|---|---|---|
| 1 | User has attached **nothing** (no datasets, no aims) | ✅ RESOLVED | ✅ Already handled | Backend guard returns "Please attach a dataset or aim" — no changes needed |
| 2 | User has attached **only one dataset** | ✅ RESOLVED | ✅ Already handled | Keep current: user types question → LLM responds with metadata only (no SQL) |
| 3 | User has attached **multiple datasets** | ✅ RESOLVED | ✅ Enhanced | Keep current + add cross-dataset analysis prompt (3 suggestions if exploratory, 1 if specific intent) |
| 4 | User has attached **dataset(s) + one aim** | ✅ RESOLVED | ✅ No pre-analysis | No auto-run. User types question → LLM works with metadata only. RUN button unchanged. |
| 5 | User has attached **datasets + multiple aims** | ✅ RESOLVED | ✅ Same as cond-4 | No auto-run. LLM works with metadata. One query at a time. |
| 6 | User attached **aim without pre-run** | ✅ RESOLVED | ✅ Same as cond-4 | No auto-run. LLM works with metadata. RUN button for real SQL. |
| 7 | User **detaches AIM** while Send is in progress | ✅ RESOLVED | ✅ Disable UI | Disable all actions during LLM processing. After response, UI re-enabled. |
| 8 | User **detaches dataset** while Send is in progress | ✅ RESOLVED | ✅ Disable UI | Same as cond-7. |
| 9 | User **sends message** while previous Send is in progress | ✅ RESOLVED | ✅ Disable UI | Block Send button during loading. One query at a time. |
| 10 | Send message **fails** (backend error) | ✅ RESOLVED | ✅ Show error | Display appropriate error message. Let user retry manually. |
| 11 | User **switches modes** while Send is in progress | ✅ RESOLVED | ✅ Disable UI | Disable mode switch during loading. |
| 12 | User **switches sessions** while Send is in progress | ✅ RESOLVED | ✅ Toast notification | Response saves to original session. Toast notifies user. Click toast to navigate back. |
| 13 | User **switches sessions** while Send is in progress | ✅ RESOLVED | ✅ Same as cond-12 | Toast notification, click to navigate back. |
| 14 | User attaches **AIM without datasets** | ✅ RESOLVED | ✅ Not a real condition | AIMs always come with datasets (from search bar or output panel). |
| 15 | User attaches **AIM with datasets not yet attached** | ✅ RESOLVED | ✅ Enhanced | Auto-attach datasets. Block manual detach for active aim. Show "This aim uses this dataset" if user tries. |
| 16 | User **asks question while auto-run** is in progress | ✅ RESOLVED | ✅ Not applicable | No auto-run (Option B). |
| 17 | User attaches AIM → sends query → attaches **another AIM** → sends another query | ✅ RESOLVED | ✅ One at a time | One query at a time. Cross-dataset prompt gives 1 suggestion if specific intent, 3 if exploratory. |
| 18 | User attaches **multiple AIMs at once** (from suggested aims) | ✅ RESOLVED | ✅ Same as cond-5 | No auto-run. User sends query manually. |

---

## Section-wise Discussion & Plans

---

### Cond-1: User has attached nothing (no datasets, no aims)

**Status:** 🟢 DESIGNED → ✅ Already handled

**Current behavior:**
Backend guard at `api.py:554` returns early: "Please attach a dataset or aim, or switch to SUMMARY mode."

**Decision:**
Keep as-is. ✅

---

### Cond-2: User has attached only one dataset

**Status:** 🟢 DESIGNED → ✅ Already handled

**Current behavior:**
User can type a question → LLM generates text response (no SQL execution).

**Decision:**
Keep current behavior. LLM works with metadata only. ✅

---

### Cond-3: User has attached multiple datasets

**Status:** 🟢 DESIGNED → ✅ Enhanced

**Current behavior:**
Same as cond-2 but with multiple datasets.

**Decision:**
Keep current behavior + add cross-dataset analysis prompt.

**Cross-dataset logic:**
- If user has NO clear intention (asks "give analysis", "what can I do?") → LLM gives **3 suggestions**
- If user HAS clear intention (asks "show me sales trends") → LLM gives **ONE analysis** with comprehensive study

**Plan:**
Add "Cross-Dataset Analysis" section to `RESEARCH_SYSTEM_PROMPT` and `CHAT_SYSTEM_PROMPT`:
- Find common columns across datasets
- Identify relationships using `join_hints`
- Propose cross-dataset analyses
- One suggestion at a time if specific intent, 3 if exploratory

**Files to modify:**
- `backend/llm_client.py` — Add cross-dataset section to `RESEARCH_SYSTEM_PROMPT`
- `backend/aims.py` — Add cross-dataset section to `CHAT_SYSTEM_PROMPT`

---

### Cond-4: User has attached dataset(s) + one aim

**Status:** 🟢 DESIGNED → ✅ No pre-analysis

**Current behavior:**
AIM appears in AimBar → User must manually click RUN button.

**Decision:**
No auto-run (Option B). User types question → LLM works with metadata only.
RUN button unchanged — real SQL query on full database.

**Why this works:**
- LLM can answer questions about data structure based on metadata
- LLM can propose SQL and analysis directions
- User has full control: RUN when ready, ask follow-up questions
- No misleading partial results

---

### Cond-5: User has attached datasets + multiple aims

**Status:** 🟢 DESIGNED → ✅ Same as cond-4

**Decision:**
No auto-run. LLM works with metadata. One query at a time.

---

### Cond-6: User attached aim without pre-run

**Status:** 🟢 DESIGNED → ✅ Same as cond-4

**Decision:**
No auto-run. LLM works with metadata. RUN button for real SQL.

---

### Cond-7, 8, 9, 11: User actions while Send is in progress

**Status:** 🟢 DESIGNED → ✅ Disable UI

**Decision:**
Disable all UI actions during LLM processing:
- Cannot detach AIM
- Cannot detach dataset
- Cannot send another message
- Cannot switch modes

**After response (good or bad):**
- UI re-enabled
- User can perform all actions

**Plan:**
- Add `loading` state check to detach buttons, Send button, mode toggle
- Show "LLM is processing..." message (reuse existing loading indicator)

---

### Cond-10: Send message fails

**Status:** 🟢 DESIGNED → ✅ Show error

**Decision:**
Show appropriate error message. Let user retry manually.

**Plan:**
- Display error message in chat area
- Error message includes: what went wrong, suggestion to retry
- User can click Send again after error

---

### Cond-12, 13: User switches sessions while Send is in progress

**Status:** 🟢 DESIGNED → ✅ Toast notification

**Decision:**
- Response saves to original session in memory
- Toast notification appears: "Response received in session {title}"
- User clicks toast → navigates back to that session

**Plan:**
- Add toast notification component (if not exists)
- On session switch during loading, store original session ID
- When response arrives, trigger toast
- Toast click handler navigates to original session

---

### Cond-14: User attaches AIM without datasets

**Status:** 🟢 DESIGNED → ✅ Not a real condition

**Decision:**
This condition doesn't arise. AIMs always come with datasets:
- From search bar: AIM includes associated datasets
- From output panel: AIM is attached to datasets it worked on

---

### Cond-15: User attaches AIM with datasets not yet attached

**Status:** 🟢 DESIGNED → ✅ Enhanced

**Current behavior:**
`useAim()` calls `storeAddMultiple()` and `storeAttachMultiple()`.

**Enhanced behavior:**
1. **Auto-attach:** If AIM's datasets are not already attached → attach them automatically ✅
2. **Detach AIM:** If user removes AIM → datasets STAY attached (don't auto-remove)
3. **Block manual detach:** User CANNOT manually detach a dataset that is attached to an active AIM
4. **Block message:** If user tries, show: "This aim uses this dataset"

**Plan:**
- Update `removeAim()` in `ChatSection.tsx:163-184`
- Check if dataset is locked by any active aim before allowing detach
- Show locked icon on datasets attached to active aims
- Disable detach button for locked datasets

---

### Cond-16: User asks question while auto-run is in progress

**Status:** 🟢 DESIGNED → ✅ Not applicable

**Decision:**
No auto-run (Option B). This condition doesn't arise.

---

### Cond-17: Multiple queries with different aims

**Status:** 🟢 DESIGNED → ✅ One at a time

**Decision:**
- One query at a time (UI disabled during loading)
- Cross-dataset prompt gives 1 suggestion if specific intent, 3 if exploratory
- Conversational flow: user can follow up, ask more, drill down

**Plan:**
- Add "ONE suggestion at a time" instruction to `RESEARCH_SYSTEM_PROMPT`
- Add "conversational tone" instruction
- Ensure LLM doesn't overwhelm with multiple ideas

---

### Cond-18: User attaches multiple AIMs at once

**Status:** 🟢 DESIGNED → ✅ Same as cond-5

**Decision:**
No auto-run. User sends query manually. One query at a time.

---

## Implementation Plan Summary

### Files to Modify

| File | Changes | Conditions |
|---|---|---|
| `backend/llm_client.py` | Add cross-dataset analysis section to `RESEARCH_SYSTEM_PROMPT` | 3, 17 |
| `backend/aims.py` | Add cross-dataset analysis section to `CHAT_SYSTEM_PROMPT` | 3, 17 |
| `frontend/src/sections/ChatSection.tsx` | Disable UI during loading (detach, send, mode switch) | 7, 8, 9, 11 |
| `frontend/src/sections/ChatSection.tsx` | Block manual detach for datasets attached to active aims | 15 |
| `frontend/src/components/AimBar.tsx` | Show locked icon on datasets attached to active aims | 15 |
| `frontend/src/components/TurnBubble.tsx` | Disable toggle buttons during loading | 7 |
| Toast notification component | Add toast for session switch notification | 12, 13 |

### Key Design Decisions

1. **No pre-analysis** — LLM works with metadata only (Option B)
2. **RUN button unchanged** — Real SQL on full database
3. **One query at a time** — UI disabled during loading
4. **Cross-dataset prompt** — 3 suggestions if exploratory, 1 if specific intent
5. **Dataset locking** — Cannot detach dataset attached to active aim
6. **Toast notification** — Session switch during loading notifies user
