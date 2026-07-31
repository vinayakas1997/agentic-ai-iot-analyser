# Save & Reuse Column Templates — Summary

## What Was Built

A complete feature allowing users to save column definitions (names + meanings) as named templates and reuse them on future CSV uploads. On upload, the system auto-matches column names against saved templates and shows the top 3 matches with similarity percentages.

### Components

1. **Column Template CRUD** (Backend) — Save, list, and delete named templates stored in PostgreSQL
2. **Auto-Matching** (Backend) — Jaccard similarity algorithm comparing uploaded column names vs saved template column names, returns top 3 matches
3. **Template Save UI** (Frontend) — "Save Template" button with inline name input in both `ColumnClarifyView` and `EditColumnsDialog`
4. **Template Dropdown** (Frontend) — `<select>` dropdown listing all saved templates; selecting one auto-applies its column meanings
5. **Auto-Match Banner** (Frontend) — On dialog open, shows matching templates as clickable pills with percentages
6. **Translation Keys** (Frontend) — 10 new EN/JA translation pairs

---

## Files Touched

| # | File | Lines | Change |
|---|------|-------|--------|
| 1 | `backend/db/models.py` | 43-56 (new) | Added `ColumnTemplate` SQLAlchemy model |
| 2 | `backend/db/init_db.py` | 99-107 (new) | Added `column_templates` CREATE TABLE |
| 3 | `backend/column_templates.py` | 1-141 (new) | New module: `save_template`, `list_templates`, `delete_template`, `match_templates` |
| 4 | `backend/api.py` | 38-46 (import), 250-260 (schemas), 950-975 (routes) | Added 4 routes + 2 Pydantic schemas + import |
| 5 | `frontend/src/api/client.ts` | 1 (import), 347-376 (new) | Added 4 API functions + type imports |
| 6 | `frontend/src/types/index.ts` | 103-115 (new) | Added `ColumnTemplate` and `TemplateMatch` interfaces |
| 7 | `frontend/src/lib/translations.ts` | 179-187 (EN), 474-482 (JA) (new) | Added 10 EN + 10 JA translation keys |
| 8 | `frontend/src/components/ColumnClarifyView.tsx` | 6, 10, 33-39, 65-80, 175-214, 373-423, 434-455 (modified) | Added template state, handlers, auto-match useEffect, toolbar buttons, matching banner |
| 9 | `frontend/src/components/EditColumnsDialog.tsx` | 1, 2, 10, 27-35, 118-180, 249-305, 316-339 (modified) | Same additions as ColumnClarifyView |

---

## API Endpoints Added

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v2/column-templates` | Save (or update) a named template |
| `GET` | `/api/v2/column-templates?user_id=` | List all templates for a user |
| `DELETE` | `/api/v2/column-templates/{id}?user_id=` | Delete a template |
| `POST` | `/api/v2/column-templates/match` | Match column names against saved templates (top 3) |

---

## Data Flow

```
CSV Upload → ColumnClarifyView opens
    ↓
1. Auto-call GET /column-templates → populate dropdown
2. Auto-call POST /column-templates/match → get top 3 matches
    ↓
Matching banner shown (if matches found):
  "Matching templates: ProdSensor (91%) · Equipment (67%) · Legacy (44%)"
    ↓
User clicks a match → meanings auto-applied by column name (case-insensitive)
    ↓
User edits meanings / uses LLM fill → clicks "Save Template"
    ↓
Inline name input appears → type name → Enter → saved to DB
    ↓
Dropdown refreshes → template available for future use
```

---

## Match Algorithm

**Jaccard similarity** on normalized (lowercase + trim) column name sets:
```
match_pct = round(|intersection| / |union| * 100, 1)
```

Only templates with `match_pct > 0` are returned, sorted descending, max 3.

---

## Bugs Found & Fixed

| Bug | File | Fix |
|-----|------|-----|
| `EditColumnsDialog.tsx` did not import `useEffect` | `EditColumnsDialog.tsx:1` | Added `useEffect` to React import |
| Template matching used column `name` field but uploaded CSVs might have different `original_name` | `column_templates.py:115` | Matching uses `name` from template definitions; frontend applies by trying both `col.name` and `col.original_name` |

---

## Verification Steps

1. Rebuild backend: `cd agentic-project && docker compose build backend && docker compose up -d backend`
2. Rebuild frontend: `docker compose build frontend && docker compose up -d frontend`
3. Upload a CSV → ColumnClarifyView opens
   - Verify matching banner appears if templates exist
   - Verify clicking a match fills meanings
4. Click "Save Template" → type name → verify template saved
5. Open template dropdown → verify it shows saved templates
6. Select a template from dropdown → verify meanings are applied
7. Upload another CSV with similar columns → verify auto-match banner works
