# Enhancement Plan 2 — Backend Reliability & Correctness (2026-07-09)

## Overview

This document details **16 issues** discovered during a deep codebase audit of the Manager Agent backend. Issues are ranked by severity: **Critical (🔴)**, **High (🟠)**, **Medium (🟡)**, **Low (🟢)**.

---

## 🔴 Issue #1 — No Error Handling on LLM Calls

### Problem
Almost every node that calls the LLM has no try/except around the `llm.ainvoke()` call. The LLM client (`llm_client.py`) does have internal retry logic with exponential backoff and a circuit breaker, but if **all retries are exhausted**, a `RuntimeError` propagates unhandled — crashing the entire graph turn with no fallback message to the user.

### Location
- `nodes/extract.py:270` — `extract_slots`: `llm.ainvoke()` call not wrapped
- `nodes/plan.py:166-169` — `reorganize_aim`: `llm.ainvoke()` not wrapped
- `nodes/advisory.py:65-68` — `answer_advisory`: `llm.ainvoke()` not wrapped
- `nodes/explore_aims.py:287` — `propose_or_refine_plans`: `llm.ainvoke()` not wrapped
- `nodes/plan.py:217-220` — `_generate_plan_benefits`: not wrapped (however, its **caller** `build_plan_message` wraps the call in try/except — this is the only one handled)

### Code
```python
# extract.py:269-278 — Typical pattern (no try/except around llm.ainvoke)
response = await llm.ainvoke(...)  # NO TRY/EXCEPT — can crash graph
try:
    extracted = parse_json_from_message(response.content or "{}")
except (json.JSONDecodeError, TypeError):
    extracted = {}
```

### Root Cause
Each node assumes the LLM call will always succeed. The LLM client absorbs transient failures via retry, but persistent failures (model down, network partition, rate limit exhaustion) are unhandled.

### Fix
Wrap each `llm.ainvoke()` call in try/except. On failure, return a user-facing error message and set a safe default state instead of crashing:
```python
try:
    response = await llm.ainvoke(messages, caller="extract_slots")
except Exception as exc:
    logger.error("LLM call failed in extract_slots: %s", exc)
    return {**state, "agent_message": "Sorry, I couldn't process that right now. Please try again.", "phase": "ask"}
```

### Priority
**🔴 Critical** — A single LLM outage crashes the entire manager pipeline for all users

### Effort
**1 hour** — Wrap 4 sites, each with consistent error handling pattern

---

## 🔴 Issue #2 — Race Condition in `save_task_definition`

### Problem
`save_task_definition` reads `MAX(version)` then inserts a new row with `version + 1`. Two concurrent requests for the same `(user_id, line_name)` will both read the same max version and produce **duplicate version numbers**, silently overwriting each other's task definitions.

### Location
- **File:** `agents/manager/db.py:284-302`

### Code
```python
async def save_task_definition(line_name: str, user_id: str, task_definition: dict) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.coalesce(func.max(TaskRegistry.version), 0)).where(
                TaskRegistry.user_id == user_id,
                TaskRegistry.line_name == line_name,
            )
        )
        max_v = result.scalar_one()
        new_version = int(max_v) + 1                  # TOCTOU window starts here
        row = TaskRegistry(
            user_id=user_id,
            line_name=line_name,
            version=new_version,
            task_definition=task_definition,
        )
        db.add(row)
        await db.commit()                              # TOCTOU window ends here
        return new_version
```

### Root Cause
No `SELECT ... FOR UPDATE`, no `UNIQUE` constraint on `(user_id, line_name, version)`, no optimistic locking. Two concurrent calls can compute the same `new_version`.

### Fix
Add a unique constraint and use `INSERT ... ON CONFLICT` or a retry loop:
```python
# Option A: Unique constraint + retry
@retry_on_conflict
async def save_task_definition(...):
    async with AsyncSessionLocal() as db:
        max_v = await db.scalar(
            select(func.max(TaskRegistry.version))
            .where(TaskRegistry.user_id == user_id, TaskRegistry.line_name == line_name)
            .with_for_update()
        )
        ...
```

### Priority
**🔴 Critical** — Silent data loss on concurrent task definitions

### Effort
**30 minutes** — Add unique constraint migration + locking

---

## 🔴 Issue #3 — No Error Handling on DB Calls in Nodes

### Problem
Every DB call in every graph node propagates exceptions unhandled. A single DB connection failure (pool exhaustion, network blip, server restart) crashes the graph turn, returning an HTTP 500 to the user with no helpful message.

### Location
- `nodes/multi_line.py:46` — `resolve_line_lookup(mention, user_id)` no try/except
- `nodes/plan.py:306-312` — `save_task_definition_node`: `await save_task_definition(...)` no try/except
- `nodes/task_reuse.py:15` — `load_task_history_for_state(state)` no try/except
- `nodes/registry.py:23` — `sync_dataset_context_for_state(slots, ...)` no try/except

### Code
```python
# multi_line.py:45-46 — No error handling
match = await resolve_line_lookup(mention, user_id)
# If DB is down, this raises -> graph crashes
```

### Root Cause
Nodes assume DB calls always succeed. No defensive programming at any of the 4 sites.

### Fix
Wrap each DB call in try/except. On failure, return a user-friendly error message:
```python
try:
    match = await resolve_line_lookup(mention, user_id)
except Exception as exc:
    logger.error("DB lookup failed: %s", exc)
    return {**state, "agent_message": "A database error occurred. Please try again.", "phase": "ask"}
```

### Priority
**🔴 Critical** — Database outages crash the entire pipeline

### Effort
**45 minutes** — 4 sites, consistent pattern

---

## 🔴 Issue #4 — Race Condition in Session Management

### Problem
`run_session_turn` performs read → process → write across multiple statements with no transaction isolation. Two concurrent requests for the same session:
1. Both read the same base state
2. Both process from the same snapshot
3. The second `save_session` **overwrites** the first with no conflict detection

Additionally, `next_turn_index` has a TOCTOU race — two concurrent calls compute the same `max(turn_index) + 1`, creating duplicate turn indices that corrupt chat history ordering.

### Location
- `agents/manager/session_service.py:29-57` — `run_session_turn`
- `agents/manager/session_db.py:183-192` — `next_turn_index`

### Code (session_service.py)
```python
async def run_session_turn(...) -> dict:
    row = await get_session_row(user_id, session_id)   # Read 1
    existing = await load_session(user_id, session_id)  # Read 2 (separate TX)
    result = await run_manager_agent(...)               # Process (no lock held)
    await save_session(user_id, session_id, result)     # Write (can overwrite)
    turn_index = await next_turn_index(...)             # Race: same index possible
```

### Code (next_turn_index)
```python
async def next_turn_index(user_id, session_id) -> int:
    result = await db.execute(select(func.max(ChatHistory.turn_index)).where(...))
    current = result.scalar_one_or_none()
    return (current if current is not None else -1) + 1   # Two calls can get same value
```

### Root Cause
No locking, no version-based optimistic concurrency for turn indices. `save_session` does use optimistic locking on the session version, but the broader read → process → write window is unguarded.

### Fix
1. Move `next_turn_index` inside the session transaction with `SELECT ... FOR UPDATE` on the session row
2. Use a DB sequence or `INSERT ... RETURNING` with a unique constraint on `(session_id, turn_index)`
3. Add a retry loop in `run_session_turn` for optimistic lock failures on `save_session`

### Priority
**🔴 Critical** — Concurrent requests silently corrupt session data and chat history

### Effort
**1.5 hours** — Add FOR UPDATE, unique constraint migration, retry logic

---

## 🟠 Issue #5 — `error` Field Never Explicitly Cleared

### Problem
The `error` field is set by nodes (`"no_datasets"`, `"line_not_found"`, `"line_ambiguous"`, `"validation_error"`, `"session_done"`) but no routing logic or intermediate node ever explicitly resets it to `None`. Once set, it persists in the graph state between turns via `_default_state` (which carries forward `base.get("error")`). While `resolve_all_lines` does overwrite it in its return dict, there is a window between `extract_slots` and `resolve_all_lines` where a stale error could influence behavior.

### Location
- **Sets error:** `multi_line.py:111`, `registry.py:33`, `runner.py:95`, `runner.py:109`
- **Carries forward:** `runner.py:53` — `"error": base.get("error")`
- **Checks error:** `routing.py:158,200,208,304,312`
- **Never clears:** `inject_reference_time`, `extract_slots`, `merge_slots`, `sync_session_context`, `sync_registry_context`, `sync_time_context`

### Code
```python
# runner.py:36-55 — _default_state carries forward error
def _default_state(existing: dict | None) -> dict:
    base = existing or {}
    return {
        ...
        "error": base.get("error"),   # Carried from previous turn, never cleared
    }
```

### Root Cause
No explicit `state.pop("error", None)` anywhere in the node pipeline. The field is set-or-nothing.

### Fix
Add `state.pop("error", None)` at the start of each major entry-point node (`inject_reference_time`, `extract_slots`, `merge_slots`), or alternatively set `"error": None` explicitly in the `_default_state` function.

### Priority
**🟠 High** — Stale errors can cause incorrect routing decisions in edge cases

### Effort
**15 minutes** — Add clear at 3-4 node entry points

---

## 🟠 Issue #6 — Confirm Detection False Positives

### Problem
`is_confirm_message` and `detect_confirm` use substring matching against word tokens. A user saying `"I don't want to go with that"` triggers confirm because `"go"` is a token in the split message. Similarly, `"you can proceed"` matches `"proceed"`, and `"ok"` matches inside words like `"okay"`, `"token"`, `"stroke"`.

### Location
- `routing.py:15-23` — `is_confirm_message`
- `plan.py:267-273` — `detect_confirm`

### Code
```python
_CONFIRM_WORDS = ("go", "confirm", "yes", "proceed", "ok")

# routing.py:15-23
def is_confirm_message(state: ManagerState) -> bool:
    if state.get("phase") != "plan":
        return False
    user_msg = (state.get("user_message") or "").lower().strip()
    return any(word == user_msg or word in user_msg.split() for word in _CONFIRM_WORDS)
    # "I don't want to go with that".split() contains "go" → FALSE POSITIVE
```

### Root Cause
Naive token-matching without negation detection or exact phrase matching.

### Fix
Option A: Require exact match on single-word messages only, and require the full message to be a confirmation phrase:
```python
# Option A: Exact match only for single-word; phrase match for multi-word
if len(tokens) == 1:
    return tokens[0] in _CONFIRM_WORDS
# Multi-word: check if message starts with confirmation phrase
return user_msg in ("go ahead", "yes please", "proceed", "confirm")
```

Option B: Add negation detection — if any negation word (`"not"`, `"don't"`, `"doesn't"`, `"won't"`) appears within 3 tokens before a confirm word, reject.

### Priority
**🟠 High** — Can silently skip user's actual intent (e.g., rejecting the plan)

### Effort
**30 minutes** — Add negation detection or stricter matching

---

## 🟡 Issue #7 — `reference_now` Not Persisted

### Problem
`reference_now` is absent from `PERSISTED_STATE_KEYS` in `session_store.py`. It is never saved to the database. On session reload (e.g., after server restart), `_default_state` gets an empty string for `reference_now`. This is partially mitigated by `inject_reference_time` which re-runs at the start of every turn, so it's not a functional bug — but it means time arithmetic for "last month" etc. is recalculated relative to the current time on each turn, which could shift between turns.

### Location
- `agents/manager/session_store.py:7-36` — `PERSISTED_STATE_KEYS`

### Code
```python
PERSISTED_STATE_KEYS = (
    "reference_timezone",   # Persisted
    # "reference_now",      # NOT persisted — missing
    "slots",
    ...
)
```

### Root Cause
Oversight when defining the persisted state keys.

### Fix
Add `"reference_now"` to `PERSISTED_STATE_KEYS`:
```python
PERSISTED_STATE_KEYS = (
    "reference_now",        # ADD
    "reference_timezone",
    "slots",
    ...
)
```

### Priority
**🟡 Medium** — Not currently a functional bug due to re-injection, but correctness issue for time-sensitive multi-turn conversations

### Effort
**5 minutes** — One-line add

---

## 🟡 Issue #8 — Chat History Deserialization Silently Corrupts

### Problem
`_dict_to_message` silently maps unknown/empty roles to `AIMessage` — a `SystemMessage`, `ToolMessage`, or any corrupted role string (e.g., `role: "system"`, `role: ""`, `role: null`) is deserialized as an AI message. Over many turns, chat history accumulates silently corrupted entries. Additionally, `_serialize_chat_history` drops non-standard message types silently, and `_deserialize_chat_history` silently filters out non-dict items.

### Location
- `agents/manager/session_store.py:49-54` — `_dict_to_message`
- `agents/manager/session_store.py:62-65` — `_serialize_chat_history`
- `agents/manager/session_store.py:72` — `_deserialize_chat_history`

### Code
```python
# session_store.py:49-54
def _dict_to_message(item: dict) -> BaseMessage:
    role = item.get("role", "")
    content = item.get("content", "")
    if role == "user":
        return HumanMessage(content=content)
    return AIMessage(content=content)   # ANY unknown role → AIMessage silently

# session_store.py:62-65 — Only checks existence, not values
elif isinstance(item, dict) and "role" in item and "content" in item:
    out.append({"role": item["role"], "content": item["content"]})
    # role="" accepted, role=123 accepted

# session_store.py:72 — Non-dict items silently filtered
return [_dict_to_message(item) for item in data if isinstance(item, dict)]
```

### Root Cause
No validation of role values, no error on unexpected data shapes.

### Fix
```python
def _dict_to_message(item: dict) -> BaseMessage:
    role = item.get("role", "")
    content = item.get("content", "")
    if role == "user":
        return HumanMessage(content=content)
    if role == "assistant" or role == "ai":
        return AIMessage(content=content)
    logger.warning("Unknown chat role '%s' — dropping message", role)
    raise ValueError(f"Unknown chat role: {role}")  # Or return None and let caller filter
```

### Priority
**🟡 Medium** — Gradual corruption over many turns; confusing debugging

### Effort
**30 minutes** — Validate roles, log warnings, add error handling

---

## 🟡 Issue #9 — `save_session` Silently Fails

### Problem
If a session row was deleted between `get_session_row` and `save_session` (race condition, manual DB intervention), `save_session` logs a warning and returns without error. The caller `run_session_turn` does not check the return value, so the graph result is silently lost — no notification to the user, no HTTP error.

### Location
- `agents/manager/session_db.py:79-81`
- `agents/manager/session_service.py:44`

### Code
```python
# session_db.py:79-81
if row is None:
    logger.warning("save_session: session %s not found for user %s", session_id, user_id)
    return   # Silent return, caller never checks

# session_service.py:44
await save_session(user_id, session_id, result)   # Return value ignored
```

### Root Cause
Caller doesn't verify the save succeeded.

### Fix
```python
# session_db.py — raise on failure
if row is None:
    raise RuntimeError(f"Session {session_id} not found")

# session_service.py — catch and handle
try:
    await save_session(user_id, session_id, result)
except Exception as exc:
    logger.error("Failed to save session: %s", exc)
    return {"agent_message": "Failed to save your session. Please try again.", "phase": "error"}
```

### Priority
**🟡 Medium** — Silent data loss in edge cases, hard to debug

### Effort
**15 minutes** — Add error propagation + handling

---

## 🟡 Issue #10 — No Validation of LLM JSON Output Shape

### Problem
`extract_slots` catches JSON parse errors but does **not validate** the structure of the parsed JSON. If the LLM returns `{"proposals": []}` or any completely unexpected shape, it is accepted as-is and fed into `_merge_extraction` which may produce silently wrong results — empty slots with no error indicator.

### Location
- `nodes/extract.py:272-278` — No structural validation after JSON parse
- `nodes/explore_aims.py:62` — `_normalize_proposals`: `int(pid)` crashes on non-numeric IDs (e.g., `{"id": "abc"}`)

### Code
```python
# extract.py:272-278 — Structure not validated
try:
    extracted = parse_json_from_message(response.content or "{}")
except (json.JSONDecodeError, TypeError):
    extracted = {}     # Silent fallback — no validation of structure
```

### Root Cause
"Parse, don't validate" approach — assumes LLM always returns the correct schema.

### Fix
```python
# Pydantic or manual validation of expected keys
EXPECTED_KEYS = {"line_mention", "time_raw", "aim_raw"}
if not EXPECTED_KEYS.issubset(extracted.keys()):
    logger.warning("LLM extraction missing keys: %s", EXPECTED_KEYS - extracted.keys())
    extracted = {}  # Or handle missing keys gracefully
```

### Priority
**🟡 Medium** — Silent failures when LLM returns wrong format

### Effort
**30 minutes** — Add structural validation in `extract_slots` + fix `int(pid)` crash

---

## 🟡 Issue #11 — `_route_explore` Silently Discards Unknown Actions

### Problem
If the LLM produces an unrecognized `aim_exploration.action` value, `_route_explore` returns `None`, silently discarding the user's intent and falling through to `ask_missing` or `resolve_time_filters` with no logging. Additionally, if the action is `"confirm"` or `"select"` but `analysis_proposals` is `None`/empty, the user's intent is also silently discarded.

### Location
- `routing.py:52-102` — `_route_explore`

### Code
```python
def _route_explore(state: ManagerState) -> str | None:
    action = _explore_action(state)
    if not action:
        return None
    if action == "save": return "save_to_shortlist"
    # ...
    if action in ("confirm", "select") and state.get("analysis_proposals"):
        return "merge_proposals_to_plan"
    return None   # Silent discard — confirm/select with no proposals, or unknown action
```

### Root Cause
Returns `None` on unknown/unhandled actions with no logging or user feedback.

### Fix
```python
if action in ("confirm", "select") and not state.get("analysis_proposals"):
    logger.warning("User confirmed but no proposals available — action=%s", action)
    return "ask_missing"  # Or return a path that explains the situation to the user
if action not in _KNOWN_ACTIONS:
    logger.error("Unknown explore action: %s", action)
    return None
```

### Priority
**🟡 Medium** — Silent intent discard, confusing UX

### Effort
**20 minutes** — Add logging + fallback routing

---

## 🟢 Issue #12 — `is_confirm_message` Over-Permissive Matching

### Problem
Same root cause as Issue #6. The word `"ok"` matches inside `"okay"`, `"token"`, `"stroke"`. The word `"go"` matches inside `"going"`, `"goal"`, `"good"`. The word `"confirm"` matches even in negated phrases like `"I cannot confirm"`. This is a duplicate/reinforcement of Issue #6 but at the routing layer specifically.

### Location
- `routing.py:15-23` — `is_confirm_message`

### Priority
**🟢 Low** — Existing bot commands already compensate, but creates subtle bugs

### Effort
**15 minutes** — Shared fix with Issue #6

---

## 🟢 Issue #13 — N+1 Query Pattern in `list_sessions`

### Status: **FALSE POSITIVE — NOT A BUG**

### Explanation
The original claim cited N+1 query behaviour in `list_sessions`. Upon inspection, this is incorrect. `list_sessions` uses a single batch subquery with `row_number() OVER (PARTITION BY session_id ORDER BY turn_index DESC)` to fetch the latest chat preview for all sessions in **one additional query**. Total DB round-trips: exactly **2**, not N+1.

### Code
```python
# session_db.py:113-162 — Efficient batched subquery
# Query 1: SELECT ... FROM manager_sessions WHERE user_id = ...
# Query 2: SELECT ... FROM (
#   SELECT *, row_number() OVER (...) as rn FROM chat_history WHERE session_id IN (...)
# ) sub WHERE rn = 1
```

### Verdict
**Not a real issue.** The existing implementation is already correctly optimized.

### Priority
N/A — Remove from tracking

---

## 🟢 Issue #14 — Prompts Have No Response Length Enforcement

### Problem
4 of 6 prompt templates have no explicit length/size instructions. While the LLM client does enforce a config-level `max_tokens` ceiling, individual prompts don't guide the model toward appropriately concise responses. Malformed or excessively long responses are displayed as-is.

### Location
- `prompts/extract_slots.md` (464 lines) — No length guide
- `prompts/reorganize_aim.md` (32 lines) — No length guide
- `prompts/propose_analysis_plans.md` (60 lines) — No length guide
- `prompts/normalize_time.md` (139 lines) — No length guide
- `prompts/advisory_answer.md` (39 lines) — ✅ Has "under 200 words"
- `prompts/plan_benefits.md` (12 lines) — ✅ Has "Under 120 words"

### Fix
Add conciseness guidance to the 4 prompts lacking it:
```markdown
# In extract_slots.md header:
Respond with a concise JSON object only, no more than 500 characters.
```

### Priority
**🟢 Low** — Cosmetic/conciseness, not a correctness issue

### Effort
**30 minutes** — 4 prompt edits

---

## 🟢 Issue #15 — No Multilingual Support

### Problem
All 6 prompt templates are English-only. The `load_prompt` function has no language parameter, no i18n/l10n mechanism, and no locale switching. Non-English user messages will produce poor extractions, time normalizations, and advisory answers with no fallback or detection.

### Location
- `agents/manager/prompts/prompts.py:1-10` — No language parameter
- `prompts/*.md` — All English, 6 files

### Code
```python
def load_prompt(name: str, **kwargs: str) -> str:
    text = (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    # No language parameter, no locale support
```

### Fix
Add a language field to the state and load localized prompts:
```python
def load_prompt(name: str, lang: str = "en", **kwargs: str) -> str:
    path = _PROMPTS_DIR / lang / f"{name}.md"
    if not path.exists():
        path = _PROMPTS_DIR / "en" / f"{name}.md"
    text = path.read_text(encoding="utf-8")
```

### Priority
**🟢 Low** — English-only is acceptable for current deployment scope

### Effort
**2-3 hours** — Add language detection, prompt directory structure, fallback logic

---

## 🟢 Issue #16 — `_distinct_line_names_by_task_alias` Fetches All Tasks

### Problem
`_distinct_line_names_by_task_alias` queries `SELECT ... FROM task_registry WHERE user_id = :user_id` with **no filter on the alias field**. All task definitions for the user are loaded into Python memory, then iterated to find alias matches. For users with many persisted task definitions (1000s), this is unnecessary memory pressure.

### Location
- `agents/manager/db.py:187-206`

### Code
```python
async def _distinct_line_names_by_task_alias(raw: str, user_id: str) -> list[str]:
    result = await db.execute(
        select(TaskRegistry.line_name, TaskRegistry.task_definition).where(
            TaskRegistry.user_id == user_id,   # No alias filter!
        )
    )
    # Fetches ALL rows into memory, filters in Python
    for line_name, task_def in result.all():
        alias = ...  # Python-side alias matching
```

### Root Cause
The `alias_name` is inside a JSON `task_definition` column, so it cannot be filtered at the DB level without a JSON path index.

### Fix
Option A: Add a PostgreSQL `JSONB` path index on `task_definition->>'alias_name'` and filter at the DB level.
Option B: Add a dedicated `alias_name` column with a GIN or B-tree index.

### Priority
**🟢 Low** — Performance issue only for users with very large task registries

### Effort
**1 hour** — Add DB index + query update

---

## Implementation Priority Order

| Phase | Issues | Total Effort | Rationale |
|-------|--------|--------------|-----------|
| **Phase 1 (Immediate)** | #1, #3 | ~1.75 hrs | LLM/DB error handling — prevents complete pipeline crashes |
| **Phase 2 (This Sprint)** | #2, #4 | ~2 hrs | Race conditions causing silent data corruption |
| **Phase 3 (Next Sprint)** | #6, #8, #9 | ~1.25 hrs | UX correctness — false confirmations, chat corruption, silent failures |
| **Phase 4 (Backlog)** | #5, #7, #10, #11 | ~1.5 hrs | Defensive hardening |
| **Phase 5 (Backlog)** | #12, #14, #15, #16 | ~4 hrs | Low-priority polishing |

---

## Verification Checklist

After each fix, verify:

- [ ] **#1** — Kill LLM endpoint mid-request — user sees "Sorry, I couldn't process that" instead of HTTP 500
- [ ] **#2** — Fire 10 concurrent `save_task_definition` calls for same line — no duplicate versions, no data loss
- [ ] **#3** — Kill database mid-request — user sees graceful error message, graph doesn't crash
- [ ] **#4** — Fire 10 concurrent message sends for same session — all turns saved, no duplicate indices, no lost updates
- [ ] **#5** — Set error in one turn, verify it's cleared at start of next turn
- [ ] **#6** — Send "I don't want to go with that" on plan phase — not confirmed; send "go" — confirmed
- [ ] **#7** — After reloading a session with time filter "last month", verify `reference_now` is persisted correctly
- [ ] **#8** — Deserialize chat history with `role: "system"` — log warning, don't silently convert to AIMessage
- [ ] **#9** — Delete session row between read and save — user sees error message, not silent success
- [ ] **#10** — Return malformed JSON from LLM — extraction falls back gracefully, doesn't crash
- [ ] **#11** — Set unknown `aim_exploration.action` — log warning, route to safe fallback
- [ ] **#12** — Same as #6
- [ ] **#14** — Verify prompts produce appropriately concise outputs
- [ ] **#15** — Send non-English message — detection works, prompt selection works
- [ ] **#16** — User with 10,000 tasks — `_distinct_line_names_by_task_alias` filters at DB level, not in Python

---

**Created:** 2026-07-09  
**Author:** Codebase Audit  
**Status:** Ready for Review
