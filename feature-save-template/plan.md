# Save & Reuse Column Templates — Plan

## Goal

Allow users to save column definitions (names + meanings) as reusable templates after editing them (manually or via LLM fill). On subsequent CSV uploads, the system auto-matches uploaded column names against saved templates and shows the top 3 matches by percentage, so users can apply a known format instantly instead of re-running LLM fill every time.

---

## File Changes

| # | File | Action |
|---|------|--------|
| 1 | `backend/db/models.py` | Add `ColumnTemplate` SQLAlchemy model |
| 2 | `backend/db/init_db.py` | Add `column_templates` table creation |
| 3 | `backend/column_templates.py` | **New** — CRUD + Jaccard matching logic |
| 4 | `backend/api.py` | Add 4 new routes: save/list/delete/match |
| 5 | `frontend/src/api/client.ts` | Add 4 API client functions |
| 6 | `frontend/src/components/ColumnClarifyView.tsx` | Add template UI (save, dropdown, auto-match banner) |
| 7 | `frontend/src/components/EditColumnsDialog.tsx` | Same template UI additions |
| 8 | `frontend/src/lib/translations.ts` | Add ~8 new EN/JA translation keys |

---

## Data Model

### `column_templates` (PostgreSQL)

```sql
CREATE TABLE column_templates (
    id                  SERIAL PRIMARY KEY,
    user_id             TEXT NOT NULL,
    template_name       TEXT NOT NULL,
    column_definitions  JSONB NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, template_name)
);
```

`column_definitions` shape matches the existing `ColumnDraft[]` type:
```json
[
  { "name": "sensor_id", "original_name": "sensor_id", "datatype": "TEXT", "meaning": "Unique sensor identifier" },
  { "name": "temperature", "original_name": "temperature", "datatype": "REAL", "meaning": "Temperature reading in Celsius" }
]
```

---

## Backend API

### `POST /api/v2/column-templates` — Save template

Request:
```json
{ "template_name": "My Production Template", "columns": [...], "user_id": "abc" }
```
Response:
```json
{ "id": 1, "template_name": "My Production Template", "column_definitions": [...] }
```

### `GET /api/v2/column-templates?user_id=abc` — List templates

Response:
```json
{ "templates": [ { "id": 1, "template_name": "...", "column_definitions": [...], "created_at": "..." } ] }
```

### `DELETE /api/v2/column-templates/{id}?user_id=abc` — Delete template

Response:
```json
{ "status": "deleted", "id": 1 }
```

### `POST /api/v2/column-templates/match` — Match columns against templates

Request:
```json
{ "column_names": ["sensor_id", "temperature", "humidity"], "user_id": "abc" }
```
Response:
```json
{
  "matches": [
    { "id": 1, "template_name": "Prod Sensor Template", "match_pct": 91, "columns": [...] },
    { "id": 2, "template_name": "Equipment Log", "match_pct": 67, "columns": [...] },
    { "id": 3, "template_name": "Legacy Format", "match_pct": 44, "columns": [...] }
  ]
}
```

**Match algorithm**: Jaccard similarity on normalized column names:
- Normalize: lowercase + trim
- `match_pct = round(|intersection| / |union| * 100)`
- Return top 3 by match_pct (descending), minimum threshold 1%

---

## Frontend UI

### ColumnClarifyView (post-upload dialog)

Current toolbar: `[Upload column meanings] [LLM fill empty]`

New toolbar: `[Upload column meanings] [LLM fill empty] [Save Template] [Dropdown ▼]`

**Auto-match on mount:**
1. Dialog opens → immediately call `POST /column-templates/match` with column names
2. If matches found, show a banner above the table:
   ```
   📋 Matching templates: Prod Sensor (91%) · Equipment (67%) · Legacy (44%)  [Dismiss]
   ```
3. Click a match → apply its column meanings (matched by column name, normalized)

**Save Template:**
1. Click "Save Template" → inline text input appears → type name → Enter/click save
2. Calls `POST /column-templates` with current columns
3. Dropdown refreshes

**Template Dropdown:**
1. Loaded from `GET /column-templates` on mount
2. Selecting a template from dropdown immediately applies its column meanings (by name match)
3. Helpful when auto-match didn't find what you want

### EditColumnsDialog (edit existing dataset)

Same toolbar additions as above.

---

## Translations (EN)

| Key | EN |
|-----|----|
| `clarify.saveTemplate` | Save Template |
| `clarify.templateNamePlaceholder` | Template name... |
| `clarify.templateSaved` | Template saved |
| `clarify.templateApplied` | Template "{name}" applied |
| `clarify.templateMatch` | Matching templates |
| `clarify.noTemplates` | No saved templates |
| `clarify.templateDeleteConfirm` | Delete template "{name}"? |
| `clarify.selectTemplate` | Select a template... |

---

## Summary Files

After implementation, a `summary.md` will be created documenting:
- What was built
- Files touched (with line numbers for changes)
- Any bugs discovered and fixed
- Verification steps
