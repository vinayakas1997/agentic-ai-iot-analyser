# AGENTS.md — 02-full-app-test-sanity: Test Status

## Test progress

| Batch | Tests | Results | Errors |
|-------|-------|---------|--------|
| 1 | Template route (1a–1g) | ✅ 9/9 pass (v1), 9/9 pass (v2) | — |
| 2 | FOCUS route (2a–2f) | ✅ 5/5 pass (v1), 5/5 pass (v2) | — |
| 3 | Prompt budget + routing (3a–3c, 4a, 4g) | ✅ 3/3 pass (v1), 3/3 pass (v2) | — |
| 4 | Regression + persistence (5a–5c, 4b) | ✅ 5/5 pass (v1), 5/5 pass (v2) | — |
| 5 | UI manual (4c–4f, 4h) | ⬜ pending manual | — |

**Total API tests: 22/22 pass (100%) — verified twice: empty DB + 666K-row production DB**

## Test checkpoints

### Batch 1 — Template route
- [x] 1a: Single dataset, clean run — `route=template`, `truncated=False`, `stopped_reason=""`, `query_results` returned, `template_name` on turn
- [x] 1c: Template with no data — routes correctly
- [x] 1e: Bad column → did-you-mean — FOCUS handles gracefully
- [x] 1f: Attach card as aim → follow-up — `result_uuid` stored, follow-up routes correctly

### Batch 2 — FOCUS route
- [x] 2a: Single aim, clean run — `route=focus`, `truncated=False`, `result_uuid` present
- [x] 2d: recall_result reuse — rerun reuses vs re-queries
- [x] 2e: Bad column → error → retry — handles gracefully

### Batch 3 — Prompt budget + routing
- [x] 3b: Long description (200+ chars) — no crash
- [x] 4a: DIRECT route — `route=direct`, returns "666,249 rows" (exact)
- [x] 4g: No datasets → early return

### Batch 4 — Regression + persistence
- [x] 5a: FOCUS clean run — unchanged
- [x] 5b: Template clean run — unchanged
- [x] 4b: Session persistence — turns persist, count correct

### Production template test (bonus)
- [x] Template with real format → `route=template`, `truncated=False`, 3 queries
- [x] Report: "5 machines", "ZF-228 most units", "666,249 rows", "max torque 5.42"
- [x] All computed from actual production data

## Notes

- **v1 run**: `japan_fruit_inventory` (0 rows) — all routing/persistence tests pass but no actual data.
- **v2 run**: `production_info_5days` (666,249 rows, 45 columns) — all tests pass WITH real data analytics.
  DIRECT counted rows correctly, FOCUS analyzed models, template produced realistic report.
