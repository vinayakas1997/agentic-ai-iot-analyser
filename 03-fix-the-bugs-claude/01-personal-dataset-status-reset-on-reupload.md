# 01 — Re-uploading a personal CSV silently demotes it from "active" back to "draft"

**Severity:** High
**Status:** fix applied, needs test
**Likely relevant to:** user_id=106761, session_id=c99346a6-8bd8-4e51-ba0a-05b25622c3c4 (best current candidate root cause for the 16-round "no data" template failure)

## Explanation

`create_draft_dataset` in `agentic-project/backend/user_datasets.py` (lines
144–157) is called whenever a user uploads a CSV. If a `UserRegistry` row
already exists for the same `user_id` + `dataset_name` (e.g. the user
re-uploads a corrected/updated version of a file they already confirmed),
the function unconditionally does:

```python
existing.table_name = table_name
existing.sqlite_path = sqlite_path
existing.original_filename = original_filename
existing.column_definitions = column_definitions
existing.column_profiling = column_profiling
existing.row_count = row_count
existing.status = "draft"   # <-- always reset, even if it was "active"
```

`fetch_active_user_datasets` (`user_datasets.py:215-236`, used by
`agentic-project/backend/api.py` when resolving datasets for a request)
only returns rows where `status == "active"`. So the moment a dataset is
re-uploaded, it disappears from dataset resolution for every session/template
that references it by name — with no user-facing message explaining why.

For the template route specifically, this compounds with bug 02: the
template agent still runs with `datasets_data=[]`, burns all
`template_max_rounds` (16, `config.py:25`) retrying failed queries, and
reports "no data" instead of surfacing "this dataset needs to be
re-confirmed after re-upload."

## Files touched (to fix)

- `agentic-project/backend/user_datasets.py` (`create_draft_dataset`, ~line 144-166)
  - Only reset `status` to `"draft"` when the schema actually changed
    (e.g. column definitions differ), or at minimum, do not silently reset
    an `"active"` row to `"draft"` without also invalidating/warning any
    session that currently references it.
  - Alternative: keep `status = "active"` on re-upload if column
    definitions are unchanged from the previous version, and require
    explicit re-confirmation only when the schema changes.

## Test plan

1. Upload a CSV as user X, confirm it (status → `"active"`).
2. Attach it to a session/template and confirm the template run succeeds
   and returns real data.
3. Re-upload the same CSV (same `dataset_name`) with a header-only change,
   without re-confirming.
4. Re-run the same template against the same session.
   - **Before fix:** dataset resolves to `datasets_data=[]`, template loops
     all 16 rounds, reports "no data" for all fields.
   - **After fix:** dataset either stays active and resolves correctly, or
     the API returns a clear "dataset needs re-confirmation" message instead
     of running the full agent loop.
5. Add a unit/integration test around `create_draft_dataset` asserting that
   re-uploading an `"active"` row with identical column definitions does not
   flip status to `"draft"` (or that whatever new behavior is chosen is
   covered).

## Current status

Fix applied in `agentic-project/backend/user_datasets.py`:
- Added `_columns_signature()` to fingerprint a dataset's columns by
  `(name, datatype)`, ignoring `meaning`.
- `create_draft_dataset` now only resets `status` to `"draft"` when the
  schema actually changed. If unchanged, it carries over previously-curated
  `meaning` values into the new column definitions (so a cosmetic re-upload
  no longer wipes out confirmed column meanings either).

Not yet run against a live DB/session — needs the manual test plan above
executed, plus confirmation this doesn't conflict with any UI flow that
assumes every upload always lands in `"draft"`.
