# AGENTS.md — 01-fix-the-project: Implementation Status

## Batch

Continues the numbering from `fix-the-bugs` (01–07) and `fix-the-bugs-batch2` (08–11).

| # | Fix | Status |
|---|-----|--------|
| 12 | Template output cards in OutputPanel | ✅ implemented & verified |
| 13 | Follow-up FOCUS reuses template query results | ✅ implemented & verified |
| 14 | Overall prompt token budget + compaction | ✅ implemented & verified |

## Status table

| # | Fix | Files touched | Status | Test errors found |
|---|-----|---------------|--------|-------------------|
| 12 | Template output cards | outputStore.ts, ChatSection.tsx, OutputPanel.tsx, client.ts, sessionStore.ts, translations.ts | ✅ done | — |
| 13 | Follow-up reuses template data | api.py, focus_agent.py | ✅ done | — |
| 14 | Prompt token budget + compaction | api.py, config.py | ✅ done | — |

## Bugs / Fix log

No test errors encountered during this batch.

## Deploy

```bash
cd agentic-project
docker compose build backend frontend
docker compose up -d backend frontend
```

Hard-refresh the browser after the frontend rebuild.

## Batch verification (2026-08-03)

### Static checks
- [x] `npx tsc -p tsconfig.app.json --noEmit` clean (0 errors)
- [x] `vite build` passes
- [x] `python3 -m py_compile api.py focus_agent.py template_agent.py config.py` clean

### Live API checks
- [x] Backend health `{"status":"ok"}`
- [x] Template route: `route=template`, `truncated=False`
- [x] Template turn stores `template_name: "Test Report"` in session state
- [x] Follow-up FOCUS with `attached_aims=["Test Report"]` routes correctly
- [x] `prompt_max_tokens=6000` confirmed from config
- [x] `template_name` field reaches backend and is stored on turn
