# Enhancement Plan 8 — Multi-Table UI Display: Datasets, Joins, Cross-Table Badge in Chat (2026-07-09)

## Overview

The UI displays line name, time range, and aims as chips in the user bubble's "Resolved" section and in the agent's plan section. However, for multi-table/cross-table scenarios, the UI was missing explicit visual indicators for **which datasets are in scope**, **how they are joined**, and **whether the query spans multiple tables**. This plan adds those visuals.

---

## Current Behavior

### User bubble "Resolved" section
- Shows `schema.line` (blue chip), `schema.datasets_in_scope` (amber chips, all same color), `schema.time` (neutral chip), `ui.plan.aims` (coral chips)
- **Gap:** All dataset chips are same color — no visual distinction between primary/secondary/tertiary roles
- **Gap:** No cross-table indicator when >1 dataset is in scope
- **Gap:** No join information shown (`schema.joins` is silently ignored)

### Agent bubble "Plan mode" section
- Shows `Line`, `Time`, `Aims` as text rows (not chips)
- **Gap:** **No datasets are shown at all** — user must look back at the user bubble's "Resolved" section to see which tables are involved
- **Gap:** No joins visualization
- **Gap:** No cross-table indicator

### Pending turn (optimistic) section
- Same chips as the user bubble but using `pendingTurn.schema`
- **Gap:** Same issues — no role coloring, no cross-table badge, no joins

---

## Root Causes

| Gap | File | Root Cause |
|-----|------|------------|
| No datasets in plan | `ChatSection.tsx:361-404` | Plan mode rendering only includes Line, Time, Aims — `datasets_in_scope` never rendered |
| Dataset chips all same color | `ChatSection.tsx:309-316` | Dataset chips hardcoded to `chipClass("amber")` regardless of `schema.datasets[].role` |
| No cross-table badge | `ChatSection.tsx:302-334` | No conditional rendering for multi-dataset case |
| No joins visible | `ChatSection.tsx` | `schema.joins` never rendered anywhere in the chat flow |
| Same gaps in pending turn | `ChatSection.tsx:496-559` | Same rendering code without role/joins/cross-table support |

---

## Proposed Changes

### Change 1 — Add `datasetAccent` helper function

New helper that maps dataset name to chip accent color based on `schema.datasets[].role`:
- `role === "primary"` → `"blue"`
- `role === "secondary"` → `"amber"`
- `role === "tertiary"` → `"coral"`
- Unknown / missing → `"amber"`

### Change 2 — Add datasets + joins + cross-table badge to plan mode

Insert before the "Aims" row in `ui?.plan?.aims` rendering:
- **Datasets:** Label + `IconDatabase` chips colored by role, with a `×N` violet cross-table badge next to the label when >1 dataset
- **Joins:** Monospaced blue pills showing `source → target on key1, key2`

### Change 3 — Enhance user bubble resolved section

- Replace hardcoded `chipClass("amber")` with `chipClass(datasetAccent(ds, schema.datasets))`
- Add violet "Cross-table" chip when `datasets_in_scope.length > 1`
- Add joins pills after aims chips (same style as plan)

### Change 4 — Enhance pending turn section

- Same changes as Change 3, using `pendingTurn.schema` and `pendingTurn.ui`

---

## Files to Modify

| File | Change |
|------|--------|
| `frontend/src/sections/ChatSection.tsx` | Add `datasetAccent` helper; modify plan mode, resolved section, and pending turn section |

---

## Behavior After Fix

### Plan mode (agent bubble)
```
Line: Sendai Line
Time: 2024-01-01 → 2024-06-30
Datasets: [blue: japan_fruit_sales] [amber: japan_fruit_inventory] [neutral: japan_supplier_quality]  ×3
Joins:
  japan_fruit_sales → japan_fruit_inventory on prefecture, fruit_name
  japan_fruit_inventory → japan_supplier_quality on supplier_id
Aims: compare fruit sales with inventory levels across suppliers
```

### User bubble "Resolved" section
Same as before but:
- Dataset chips colored by role (primary=blue, secondary=amber, tertiary=coral)
- "Cross-table" badge when multi-table
- Join pills below aims chips

### Pending turn
Same enhancements during optimistic rendering

---

## Verification Checklist

- [ ] Plan section shows dataset chips with role-based colors
- [ ] Plan section shows cross-table `×N` badge when >1 dataset
- [ ] Plan section shows join pills with source → target on keys
- [ ] User bubble chips use role-based colors instead of all-amber
- [ ] User bubble shows "Cross-table" chip for multi-dataset turns
- [ ] User bubble shows join pills after aims
- [ ] Pending turn has same enhancements
- [ ] Single-dataset turns show no cross-table badge (no false positive)
- [ ] Turns with no joins show no join pills (no false positive)
- [ ] TypeScript compiles with no errors
- [ ] Vite build succeeds
