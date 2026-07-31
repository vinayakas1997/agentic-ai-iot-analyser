# Step 3 — Backend: registry persistence (source_config + data_earliest_ts)

> Status: DONE

## What was done

In `backend/registry_admin.py`:

1. **`create_draft_entry()`** now accepts `source_config: dict | None` and
   `data_earliest_ts: datetime | None`.
   - External DB entries: `source_config = {"connection_id", "db_type", "schema", "table"}`
     and `source_type = "external"`.
   - Main-DB entries: unchanged `source_config = {"table": ...}` and `source_type = "pg"`.
   - `data_earliest_ts` now persisted on the `GlobalRegistry` row (field existed at `db/models.py:25`
     but was previously never written).
   - Works for both insert and update (re-registration of same line+dataset) paths.

2. **`list_entries()`** now surfaces `connection_id`, `db_type`, and `data_earliest_ts` in the
   response so the UI can show which connection a dataset came from.

3. In `backend/api.py`, `registry_create_entry` builds the `source_config` (looks up the connection
   row to grab db_type/schema) and parses `data_earliest_ts` before calling `create_draft_entry`.

## Test results

- `python3 -m py_compile` → **pass**.
- Runtime verification deferred to Step 9.

## Bugs fixed while building

- **source_type mislabeled:** old code hardcoded `source_type = "pg"`; now external entries are
  tagged `"external"` so downstream query routing can distinguish them (Step 4).
- **Earliest ts parse errors:** the route rejects malformed ISO strings with a 400 instead of
  crashing the request.
