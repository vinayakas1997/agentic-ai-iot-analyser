# README — Template output cards + follow-up reuse + prompt token budget

Third-party evaluation of the template-report feature surfaced three integration gaps that
were never built (not bugs — deliberate isolation that was never reconciled). This folder
documents each fix following the same pattern as `../fix-the-bugs` and
`../fix-the-bugs-batch2`.

| # | File | Summary |
|---|------|---------|
| 12 | `12-template-output-cards.md` | Template runs create OutputPanel cards (per-template counter, badge, report + all tables) |
| 13 | `13-template-followup-reuse.md` | Follow-up FOCUS recalls template query results by template_name |
| 14 | `14-prompt-token-budget.md` | Overall prompt token budget + compaction (oldest lines drop first) |

Each file explains the **problem**, the **fix**, **files touched**, and how it was **verified**.

## Design principles

1. **Enrich only what's needed:** explanation, dataset names, SQL query — rows are fetched
   on demand via `recall_result`. Never embed `query_results` in prompts.
2. **Keep descriptions short:** template card `description` = template name only, not the
   report text.
3. **Budget the prompt:** one `estimate_tokens`-based cap over the composed enrichment block,
   dropping oldest lines first.

## Out of scope

- Card "re-run template" (cards don't carry `format_spec`).
- Global cross-session counter (counter is per-session, consistent with `output_results`).
- Changing Run-button vs composer+template behavior (kept separate).

## Deploy

```bash
cd agentic-project
docker compose build backend frontend
docker compose up -d backend frontend
```

Hard-refresh the browser after the frontend rebuild.

## Batch verification (2026-08-03)

- `npx tsc -p tsconfig.app.json --noEmit` — clean (0 errors).
- `vite build` — passes.
- `python3 -m py_compile api.py focus_agent.py template_agent.py config.py` — clean.
- Backend health `{"status":"ok"}`.
- Live API: template route returns `route=template`, turn stores `template_name`.
- Live API: follow-up FOCUS routes correctly with attached aim matching template name.
- Config: `prompt_max_tokens=6000` confirmed.
