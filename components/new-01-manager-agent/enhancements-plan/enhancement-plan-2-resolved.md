# Enhancement Plan 2 — Resolution Summary

All 11 actionable issues from `enhancement-plan-2.md` implemented.  
Verification: `tsc --noEmit` ✓, `vite build` ✓, all 14 modified backend files AST parse ✓.

---

## Phase 1 — Error Handling (Issues #1, #3)

### Issue #1 — LLM Error Handling
Wrapped `llm.ainvoke()` calls in try/except at 4 locations:

| File | Function | Change |
|------|----------|--------|
| `agents/manager/nodes/extract.py:270` | `extract_slots` | Return `{**state, "error": "llm_failed", ...}` |
| `agents/manager/nodes/advisory.py:68` | `answer_advisory` | Return `{**state, "error": "llm_failed", ...}` |
| `agents/manager/nodes/plan.py:168` | `reorganize_aim` | Return `{**state, "error": "llm_failed", ...}` |
| `agents/manager/nodes/explore_aims.py:290` | `propose_or_refine_plans` | Return `{**state, "error": "llm_failed", ...}` |

### Issue #3 — DB Error Handling
Wrapped DB calls in try/except at 4 locations:

| File | Function | Change |
|------|----------|--------|
| `agents/manager/nodes/multi_line.py:46` | `resolve_all_lines` | Wrap `resolve_line_lookup()`, mark slot `not_found` on failure |
| `agents/manager/nodes/plan.py:310` | `save_task_definition_node` | Wrap `save_task_definition()` |
| `agents/manager/context/task_history.py:11` | `fetch_task_history` | Wrap `fetch_task_versions()`, return `[]` on failure |
| `agents/manager/registry_context.py:480` | `sync_dataset_context_for_state` | Wrap `fetch_fn()`, set `error_info` on failure |

---

## Phase 2 — Race Conditions (Issues #2, #4)

### Issue #2 — save_task_definition Race
`db.py:save_task_definition()` — SELECT-MAX-then-INSERT pattern vulnerable to duplicates.  
**Fix:** Added 3-attempt retry loop catching `IntegrityError` from the `(user_id, line_name, version)` unique constraint.

### Issue #4 — next_turn_index Race
`session_db.py:next_turn_index()` ran in a separate transaction from `append_chat_turn()`, allowing concurrent calls to get the same `turn_index`.  
**Fix:** Moved `MAX(turn_index)` inside the same transaction as the INSERT in `append_chat_turn()`. Removed external `next_turn_index()` call from `session_service.py`.

---

## Phase 3 — UX Robustness (Issues #5, #6, #8, #9)

### Issue #5 — Stale Error Field
The `error` key in state persisted between turns, causing stale error displays.  
**Fix:** Added `state = {**state, "error": None}` at 8 entry point nodes:
- `extract_slots`, `answer_advisory`, `propose_or_refine_plans`, `reorganize_aim`
- `detect_confirm`, `build_plan_message`, `resolve_all_lines`, `resolve_time_filters`

### Issue #6 — Confirm False Positives
`detect_confirm` matched confirm words inside longer messages (e.g. "go to next step").  
**Fix:** Changed `any(word in user_msg.split())` to exact single-word match `user_msg in _CONFIRM_WORDS`.

### Issue #8 — Chat History Deserialization
`_dict_to_message()` didn't handle `SystemMessage` role, converting system prompts to `AIMessage`. Non-string `content` (LangChain v0.3+ lists) was silently corrupted.  
**Fix:** Added `"system"` → `SystemMessage` mapping, non-string content fallback, and `json` import.

### Issue #9 — save_session Silent Failure
When session row was `None` (not found), the function logged a warning and returned, silently dropping the state update.  
**Fix:** Changed to `raise ValueError()`. The call site already validates existence via `get_session_row()`.

---

## Phase 4 — Persistence & Reliability (Issues #7, #10, #11)

### Issue #7 — reference_now Not Persisted
`reference_now` was missing from `PERSISTED_STATE_KEYS`, causing time drift on session reload.  
**Fix:** Added `"reference_now"` to the tuple in `session_store.py`.

### Issue #10 — LLM JSON Validation
`parse_json_from_message()` could return non-dict values (`None`, `str`, list) when LLM returned malformed JSON like `null` or `"text"`.  
**Fix:** Added `isinstance(result, dict)` check after every `json.loads()`, returning `{}` for non-dict results.

### Issue #11 — _route_explore Silent Discard
When `action` was `"confirm"`/`"select"` but `analysis_proposals` was empty, `_route_explore` returned `None`, silently dropping the explore intent.  
**Fix:** `"confirm"`/`"select"` without proposals now falls through to `"propose_or_refine_plans"` instead of returning `None`.

---

## Phase 5 — Skipped (Issues #12, #14, #15, #16)

| Issue | Reason |
|-------|--------|
| #12 — LLM context length | Already handled by `get_recent_chat_messages()` with configurable window |
| #14 — Multilingual | Requires prompt template changes, out of scope |
| #15 — task_alias query perf | Requires DB migration (index/column) |
| #16 — fetch_task_versions perf | Existing usage limits to 5 rows, adequate |

---

## Files Modified

### Backend (14 files)
- `agents/manager/session_db.py` — next_turn_index atomicity, save_session error
- `agents/manager/session_store.py` — reference_now persisted, SystemMessage handling, JSON validation
- `agents/manager/session_service.py` — removed redundant next_turn_index call
- `agents/manager/json_parse.py` — non-dict result validation
- `agents/manager/db.py` — save_task_definition retry loop, IntegrityError import
- `agents/manager/registry_context.py` — fetch_fn error handling, logger
- `agents/manager/context/task_history.py` — fetch_task_versions error handling
- `agents/manager/routing.py` — _route_explore confirm/select fallback
- `agents/manager/nodes/extract.py` — LLM try/except, error field clear
- `agents/manager/nodes/advisory.py` — LLM try/except, error field clear, logger
- `agents/manager/nodes/explore_aims.py` — LLM try/except, error field clear, logger
- `agents/manager/nodes/plan.py` — LLM try/except, error field clear, exact confirm match
- `agents/manager/nodes/multi_line.py` — DB try/except, error field clear, logger
- `agents/manager/nodes/time.py` — error field clear

### Frontend (0 files — unchanged in this pass)
