# README — Safe bug fixes batch

Folder for write-ups of safe correctness/perf fixes that do **not** intentionally change product LLM behavior (FOCUS rounds, chart LLM, action extraction, etc.).

| # | File | Summary |
|---|------|---------|
| 01 | `01-message-save-retry-no-re-llm.md` | Backend retries message save without re-LLM |
| 02 | `02-remove-withretry-from-llm-endpoints.md` | Frontend stops replaying LLM APIs on 409 |
| 03 | `03-summarizing-tags-no-early-unlock.md` | No 5s early unlock of in-flight summarize |
| 04 | `04-multi-tag-summarize-timers.md` | Per-tag summarize timers |
| 05 | `05-triggersummary-userid-deps.md` | Fix stale userId in summarize callback |
| 06 | `06-toplevel-sqlalchemy-select-import.md` | Top-level `select` import |
| 07 | `07-summarize-failure-backoff.md` | 30s backoff after summarize failure |

## Intentionally NOT changed (would alter product behavior)

- Reducing FOCUS max_rounds / SQL critic loop / `extract_analysis_actions` / chart LLM
- Full versioned PATCH on `/sessions` (needs careful merge design; can increase 409s if done alone)

## Deploy

```powershell
cd agentic-project
docker compose -f docker-compose.app.yml build backend frontend
docker compose -f docker-compose.app.yml up -d backend frontend
```

Hard-refresh the browser after frontend rebuild.

## Batch verification (2026-08-03)

- `docker compose ... build backend frontend` — success (Vite build OK, images rebuilt)
- Containers `agentic-project-backend-1` / `frontend-1` — Up
- Backend log: `Application startup complete` / Uvicorn on `:7010`
- No `NameError` / no LLM spam in idle logs after restart
- Code checks: `withRetry` only on PATCH; summarize 5s unlock gone; per-tag timers + 30s backoff present
