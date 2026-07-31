# Step 2 — Backend: DB-connection API routes + introspect connection_id

> Status: DONE

## What was done

In `backend/api.py`:

1. Imported `db_connections` helpers (get/create/list/delete/test/list_tables/introspect_table/execute_sql_on)
   and `ConnectionNotFoundError`.
2. Added `CreateDbConnectionRequest` model (name, db_type, host, port, database_name, username,
   password, schema_name).
3. Extended `IntrospectRequest` with optional `connection_id` (defaults to main DB → current behavior).
4. Extended `CreateRegistryEntryRequest` with `connection_id` and `data_earliest_ts`.
5. Added routes (all IoT-role protected via `_require_iot_role` + `_require_user_id`):
   - `POST /api/v2/db-connections` — create (rejects non postgres/mysql)
   - `GET /api/v2/db-connections` — list
   - `DELETE /api/v2/db-connections/{id}` — delete
   - `POST /api/v2/db-connections/{id}/test` — live reachability test → `{ok, latency_ms, error?}`
   - `GET /api/v2/db-connections/{id}/tables` — dropdown list of tables in the connection's schema
6. Reworked `POST /api/v2/registry-admin/introspect`:
   - When `connection_id` provided → introspects that external connection (columns + sample +
     auto-detected `data_earliest_ts` / `data_earliest_col`).
   - Otherwise → main Postgres (existing behavior preserved).
   - LLM column-meaning drafting (`draft_column_meanings`) runs in both paths.
   - Response now includes `data_earliest_ts` + `data_earliest_col`.

## Test results

- `python3 -m py_compile api.py registry_admin.py db_connections.py` → **pass**.
- Runtime testing of the new routes deferred to Step 9 (needs rebuilt backend + live DBs).

## Bugs fixed while building

- **Role enforcement on GET list:** the list route is intentionally public-ish (like `list_datasets`),
  but test/tables/delete require an IoT user; kept the test route using a `user_id` query param so
  the frontend request helper can pass it the same way `deleteRegistryEntry` already does.
- **dialect/schema default drift:** the `source_config.schema` written at registration is computed to
  match the introspection schema (`public` for PG, `database_name` for MySQL when no explicit schema),
  so a dataset registered from MySQL introspects and later queries the same schema.
- **Naive ISO timestamps:** `data_earliest_ts` parsed with `fromisoformat`; if timezone-naive, forced
  to UTC before writing to the `TIMESTAMPTZ` column to avoid asyncpg ambiguity.
