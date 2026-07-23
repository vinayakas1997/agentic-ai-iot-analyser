# E2E Test Rules — Condition Management & UI Locking Implementation

## Environment Setup

- **Backend:** `cd agentic-project/backend && python -m uvicorn api:app --reload` (port 7010)
- **Frontend:** `cd agentic-project/frontend && npx vite` (port 5173)
- **Database:** PostgreSQL via asyncpg (configured in `config.py`)
- **LLM:** Ensure LLM endpoint is reachable (configured in `config.py`)

## General Testing Rules

1. **Reset state between scenarios** — Use a fresh session for each scenario. Clear localStorage and delete session records.
2. **Check API responses** — Use browser DevTools Network tab to inspect request/response payloads.
3. **Check Zustand state** — In browser console: `useSessionStore.getState()`, `useOutputStore.getState()`, `useDatasetStore.getState()`, `useToastStore.getState()`
4. **Check DB directly** — Query the `manager_sessions` table to verify `state_json`, `version` column.
5. **Check UI state** — Verify which elements are disabled/active based on `loading` state.
6. **Check console errors** — Watch for 409 retries, 500 errors, or uncaught exceptions.
7. **Run in both modes** — Every feature that differs between RESEARCH/SUMMARY must be tested in both.
8. **Verify UI locking** — During `loading: true`, ALL interactive elements should be disabled (mode switch, detach, suggested aims, send, run, remove).
9. **Verify dataset locking** — Datasets attached to active aims should show locked icon and disabled detach button.
10. **Verify toast** — When session switches during loading, toast should appear with click-to-navigate.

## What to Verify Per API Call

| Endpoint | Key Checks |
|----------|------------|
| `POST /api/v2/messages` | `history: []` sent; `enrichment_mode` present; `attached_aims` correct; cross-dataset prompt included when multiple datasets |
| `POST /api/v2/execute-query` | SQL generation + execution + chart suggestions all present |
| `POST /api/v2/sessions/{id}/summarize-context` | Idempotency (existing summary returned); versioned write |
| `PATCH /api/v2/sessions/{id}` | Shallow merge behavior |
| `POST /api/v2/sessions` | UUID returned, version = 1 |
| `GET /api/v2/sessions/{id}` | Full `state_json` with turns, summaries, results |

## Bug Reference

| ID | Bug | Severity | File:Line | Status |
|----|-----|----------|-----------|--------|
| B7 | `sessionId` renamed in destructuring but old ref on line 289 | HIGH | `sessionStore.ts:289` | ✅ FIXED |
| B8 | `queryResult.row_count` possibly undefined | LOW | `QueryActions.tsx:518` | ✅ FIXED |

## How to Update STATUS.md

After running each scenario:
1. Change the status to one of: `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, `NOT RUN`
2. Add a one-line summary of actual result
3. Reference any bugs found (e.g., "FAIL — B7 triggered")
4. Date-stamp the entry

## Code Reference Map

| Component | File | Lines | Key Functions |
|-----------|------|-------|---------------|
| ChatSection | `ChatSection.tsx` | full file | `handleSend()`, `useAim()`, `removeAim()`, `handleRunAimSql()` |
| Session Store | `sessionStore.ts` | full file | `sendUserMessage()`, `bootstrap()`, `switchSession()` |
| Toast Store | `toastStore.ts` | all | `pushToast()`, `dismissToast()` |
| ToastContainer | `ToastContainer.tsx` | all | Renders toasts, handles click-to-navigate |
| Dataset Store | `datasetStore.ts` | full file | `toggle()`, `detach()`, `lockedByAims` |
| API Client | `client.ts` | full file | `sendMessage()`, `executeQuery()`, `withRetry()` |
| TurnBubble | `TurnBubble.tsx` | full file | Toggle states, `loading` prop disables all |
| AimBar | `AimBar.tsx` | full file | `loading` prop disables remove/RUN |
| Backend API | `api.py` | full file | `send_message()`, `build_enrichment_block()` |
| LLM Client | `llm_client.py` | full file | Cross-dataset prompt section |
