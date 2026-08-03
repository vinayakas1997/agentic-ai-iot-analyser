# 02-full-app-test-sanity — App sanity results

## Summary
**22/22 API tests pass (100%)** — verified twice: empty DB (v1) + 666K-row production DB (v2).

## Test environment
- Backend: `http://localhost:7010`
- Frontend: `http://localhost:7008`
- Datasets:
  - `japan_fruit_inventory` (14 cols, 0 rows)
  - `production_info_5days` (45 cols, 666,249 rows) — loaded from 5 daily CSV files
- User: `testuser1`
- Date: 2026-08-03

## Batch results (v2 — real data)

| # | Batch | Tests | Passed | Failed | Status |
|---|-------|-------|--------|--------|--------|
| 1 | Template route (1a–1g) | 9 | 9 | 0 | ✅ |
| 2 | FOCUS route (2a–2f) | 5 | 5 | 0 | ✅ |
| 3 | Prompt budget + routing (3a–3c, 4a, 4g) | 3 | 3 | 0 | ✅ |
| 4 | Regression + persistence (5a–5c, 4b) | 5 | 5 | 0 | ✅ |
| 5 | UI manual (4c–4f, 4h) | — | — | — | ⬜ |

## Key findings (with real data)

- **DIRECT route**: "The dataset contains 666,249 rows" — exact count.
- **FOCUS route**: Analyzed models — "Model 8: 303,388 units (highest)".
- **Template route**: Production report with real data — "5 machines", "ZF-228 most units", "average torque 0.064", "max torque 5.42", 3 queries executed.
- **recall_result reuse**: Rerun correctly reuses vs re-queries.
- **Prompt budget**: Long aim descriptions (200+ chars) handled without crash.
- **Persistence**: Turns + template_name survive session state reload.
- **No-dataset guard**: Returns error early without LLM call.
- **Bad column**: Error handled gracefully with did-you-mean.

## Data loading note

`production_info_5days` was loaded from 5 daily CSV files (July 6-10, 2026):
- 131,451 + 121,262 + 138,254 + 132,007 + 143,275 = **666,249 rows**
- 45 columns with Japanese names and meanings from `生産情報_02_he.csv`
- Registered in GlobalRegistry with column definitions

## Files

| File | Purpose |
|------|---------|
| `README.md` | This file |
| `AGENTS.md` | Test status tracker with detailed checkpoints |
| `test-api.sh` | Automated curl-based API test script |
| `manual-ui-checklist.md` | Manual browser test checklist |
| `results/batch1.txt` – `results/batch4.txt` | Raw test output logs (v1 — empty DB) |
| `results/batch1-v2.txt` – `results/batch4-v2.txt` | Raw test output logs (v2 — 666K rows) |
