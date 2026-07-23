# Phase 3: Agentic Memory Gap, DIRECT Mode Fix, DEBUG System

> Created: 2026-07-23
> Status: IN PROGRESS

---

## 1. Gap Analysis

### Critical Gap: Agentic Memory Not Used by Route Handlers

The enrichment/context system (Phase 2) was fully implemented:
- `build_enrichment_block()` builds context from session state (summaries + raw turns + query results)
- `generate_chat_response()` accepts `enrichment_block` and injects it into the system prompt
- SUMMARY mode correctly uses enrichment (lines 888-903 in `api.py`)

**BUT**: The RESEARCH mode route handlers (`_handle_direct`, `_handle_suggest`, `_handle_focus`, `_handle_deep`) completely bypass enrichment. They call `_build_context()` which only returns dataset schemas — NO session history.

```
RESEARCH mode send_message flow:

1. classify_route() → DIRECT/SUGGEST/FOCUS/DEEP
2. handler = route_handlers[route]
3. handler_result = await handler(
     message, datasets, aims
   )

❌ enrichment_block NOT passed to handler
❌ handler calls _build_context() → schemas only, no previous turns/summaries
❌ LLM has ZERO memory of conversation
```

**Impact:**
- Follow-up questions fail ("show me the results for X" → LLM doesn't know what X is)
- LLM defaults to returning suggestions instead of SQL
- `aim_proposals` always empty because LLM never generates actionable content
- User sees no clickable aim titles

### Gap 2: DIRECT Mode Not Generating SQL

The `DIRECT_PROMPT` says "write a SQL query" but the LLM ignores it and returns numbered text suggestions. This is because:
1. The LLM has no context (see Gap 1), so it can't write meaningful SQL
2. The prompt isn't strong enough — it doesn't explicitly forbid suggestions
3. No fallback mechanism when SQL extraction fails

### Gap 3: No Observability

No DEBUG system exists. When things go wrong, there's no way to see:
- What route was chosen
- What prompt was sent to the LLM
- What the LLM responded
- How long each step took
- Whether SQL was extracted

---

## 2. Solution

### Fix A: Agentic Memory in Route Handlers

**File: `backend/api.py`**

1. Modify all 4 route handlers to accept `enrichment_block` parameter
2. When `enrichment_block` is present, append it to the system prompt as "## Previous Context"
3. Build enrichment block BEFORE routing (move up from SUMMARY path)
4. Pass enrichment block to all handlers in the dispatch

### Fix B: DIRECT Mode — Force SQL Execution

**File: `backend/llm_client.py`**

1. Strengthen `DIRECT_PROMPT`:
   - "CRITICAL: You MUST output a SQL query in a ```sql code block"
   - "Do NOT output numbered analysis suggestions — that is SUGGEST mode"
   - "If the question is ambiguous, respond with exactly: NONE"
   - Negative examples

2. Add `parse_numbered_suggestions()` regex parser

**File: `backend/api.py`**

3. `_handle_direct`: When SQL extraction fails, call `parse_numbered_suggestions()` as fallback, return proposals
4. `_handle_suggest`: Call `parse_numbered_suggestions()` after LLM response, return proposals

### Fix C: DEBUG/LOG System

**File: `backend/config.py`**
- Add `debug: bool = False` and `log_level: int = 0` to Settings

**File: `backend/.env.example`** + **`docker-compose.yml`**
- Add `DEBUG` and `LOG_LEVEL` env vars

**File: `backend/logger.py`** (new)
- Level 0: Standard Python logging (current)
- Level 1 (console): Enhanced output — route classification, LLM timing, SQL extraction, aim extraction
- Level 2 (file): Full logs in `logs/` folder — prompt, LLM response, SQL, timing

---

## 3. Bugs Found

| Bug | Location | Impact | Severity |
|-----|----------|--------|----------|
| Enrichment bypassed in RESEARCH | `api.py:970-985` | No conversation memory | Critical |
| DIRECT LLM not generating SQL | `llm_client.py:42` | No query results, no clickable aims | Critical |
| `_handle_suggest` never extracts proposals | `api.py:643-659` | SUGGEST route never produces aim_proposals | High |
| No observability | All backend | Cannot diagnose issues | Medium |

---

## 4. Test Results

> To be filled after implementation

## 5. Files Modified

| File | Changes |
|------|---------|
| `backend/api.py` | Add `enrichment_block` to handlers, build enrichment before routing |
| `backend/llm_client.py` | Strengthen DIRECT_PROMPT, add `parse_numbered_suggestions()`, debug logging |
| `backend/config.py` | Add `debug` and `log_level` settings |
| `backend/logger.py` | New file — structured debug logger |
| `backend/.env.example` | Add `DEBUG` and `LOG_LEVEL` |
| `docker-compose.yml` | Add `DEBUG` and `LOG_LEVEL` env vars |
