# E2E Test Rules — Tagged Context Enrichment System

## Environment Setup

- **Backend:** `cd agentic-project/backend && python -m uvicorn api:app --reload` (port 8000)
- **Frontend:** `cd agentic-project/frontend && npx vite` (port 5173)
- **Database:** PostgreSQL via asyncpg (configured in `config.py`)
- **LLM:** Ensure LLM endpoint is reachable (configured in `config.py`)

## General Testing Rules

1. **Reset state between scenarios** — Use a fresh session for each scenario. Delete session records if needed.
2. **Check API responses** — Use browser DevTools Network tab to inspect request/response payloads for every API call.
3. **Check Zustand state** — In browser console: `useSessionStore.getState()`, `useOutputStore.getState()`, `useDatasetStore.getState()`
4. **Check DB directly** — Query the `manager_sessions` table to verify `state_json`, `version` column, and `chat_query_results`.
5. **Check UI state** — Verify which elements are visible/hidden based on `enrichmentMode`. Use `data-*` attributes for reliable selectors.
6. **Check console errors** — Watch for 409 retries, 502 summaries, or any uncaught exceptions.
7. **Run in both modes** — Every feature that differs between RESEARCH/SUMMARY must be tested in both.
8. **Verify enrichment block** — Check backend logs for "Enrichment block" and "History replaced by enrichment" messages.
9. **Verify no enrichment** — Check backend logs for "Sending history within enrichment mode" when enrichment is empty.
10. **Verify version increment** — After each write operation, `session.version` should increase by exactly 1.

## What to Verify Per API Call

| Endpoint | Key Checks |
|----------|------------|
| `POST /api/v2/messages` | `history: []` sent; `enrichment_mode` present; `attached_aims` correct; response has `aim_proposals`, `analysis_actions` |
| `POST /api/v2/execute-query` | SQL generation + execution + chart suggestions all present |
| `POST /api/v2/sessions/{id}/summarize-context` | Idempotency (existing summary returned); versioned write |
| `PATCH /api/v2/sessions/{id}` | Shallow merge behavior |
| `POST /api/v2/sessions` | UUID returned, version = 1 |
| `GET /api/v2/sessions/{id}` | Full `state_json` with turns, summaries, results |

## Bug Reference (B1–B6)

| ID | Bug | Severity | File:Line |
|----|-----|----------|-----------|
| B1 | SUMMARY mode blocked by dataset guard when no datasets attached | HIGH | `api.py:556` |
| B2 | OutputPanel "+ Add"/"Added" toggle does NOT detach orphaned datasets on remove | MEDIUM | `OutputPanel.tsx:91-103` |
| B3 | `handleRunAimSql` synthetic turns use UUID as `created_at`, mismatched with summary trigger's timestamp-based counting | MEDIUM | `ChatSection.tsx:335` |
| B4 | `bootstrap()` doesn't call `datasetStore.clear()` before restore (unlike `switchSession()`) | LOW | `sessionStore.ts:131-189` |
| B5 | `generate_aim` imported in api.py but may not be defined anywhere | HIGH | `api.py:12` |
| B6 | `updateSession` shallow merge could overwrite nested `context_summaries` instead of deep-merging | MEDIUM | `api.py:464` |

## How to Update STATUS.md

After running each scenario:
1. Change the status to one of: `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, `NOT RUN`
2. Add a one-line summary of actual result
3. Reference any bugs found (e.g., "FAIL — B1 triggered, SUMMARY mode blocked")
4. Date-stamp the entry

## Code Reference Map

| Component | File | Lines | Key Functions |
|-----------|------|-------|---------------|
| ChatSection | `ChatSection.tsx` | full file | `handleSend()`, `handleRunAimSql()`, `useAim()`, `removeAim()`, `triggerSummary()`, `persistTurns()` |
| Session Store | `sessionStore.ts` | full file | `sendUserMessage()`, `bootstrap()`, `switchSession()`, `turnFromResponse()` |
| API Client | `client.ts` | full file | `sendMessage()`, `executeQuery()`, `summarizeContext()`, `withRetry()` |
| TurnBubble | `TurnBubble.tsx` | full file | Toggle states: Add/Added/Completed+Added/View |
| OutputPanel | `OutputPanel.tsx` | full file | Result cards, "+ Add" toggle, "Show Context" |
| Backend API | `api.py` | full file | `send_message()`, `build_enrichment_block()`, `summarize_context()` |
| Aims | `aims.py` | full file | `generate_chat_response()`, SQL gen/critique/fix |
| LLM Client | `llm_client.py` | full file | `summarize_turns()`, `build_enrichment_system_prompt()` |
