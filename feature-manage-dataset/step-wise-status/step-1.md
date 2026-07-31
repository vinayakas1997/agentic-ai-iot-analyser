# Step 1 — Backend: DbConnection model, table, dependency, module

> Status: DONE

## What was done

1. **`backend/db/models.py`** — added `DbConnection` SQLAlchemy model (`db_connections` table):
   `id`, `name`, `db_type` (postgres|mysql), `host`, `port`, `database_name`, `username`,
   `password`, `schema_name` (nullable, default `public`), `created_at`, `updated_at`.
   No owner column → shared across all IoT users (decision from discussion.md).

2. **`backend/db/init_db.py`** — added `CREATE TABLE IF NOT EXISTS db_connections` inside
   `create_tables()`, so it is created automatically on container start (no manual migration;
   the docker-entrypoint runs `python -m db.init_db` every boot).

3. **`backend/requirements.txt`** — added `asyncmy>=0.2.9` (async MySQL driver for SQLAlchemy).

4. **`backend/db_connections.py`** (new module) —
   - CRUD: `create_connection`, `get_connection`, `list_connections`, `delete_connection`
     (delete also disposes the cached engine).
   - Engine/DSN: `build_engine` (cached per connection id), URL-encodes user/password,
     short connect timeouts for live testing, `pool_pre_ping`.
   - Live test: `test_connection` → `SELECT 1`, returns `{ok, latency_ms, error?}`.
   - Introspection: `list_tables` (information_schema, PG + MySQL), `introspect_table`
     → `{table_name, schema, columns, sample_rows, data_earliest_ts, data_earliest_col}`.
     Earliest-timestamp detection scans date/datetime/timestamp columns and takes the
     minimum `MIN()` value across them.
   - Live execution: `execute_sql_on` → same result shape as `sql_executor.execute_sql`
     (columns, column_types, rows, row_count), reuses `validate_sql` for safety.
   - `_serialize_row` converts `Decimal` → `float` so responses are JSON-safe.

## Test results

- `python3 -m py_compile` on `db/models.py`, `db/init_db.py`, `db_connections.py` → **pass** (no errors).
- Full runtime testing deferred to Step 9 (requires rebuilt backend container + a live MySQL/PG to test against).

## Bugs fixed while building

- **MySQL `schema` semantics:** in MySQL a "database" and "schema" are the same thing. Handled by
  defaulting the introspection schema to `database_name` for MySQL and `public` for PostgreSQL when
  `schema_name` is not provided (`_schema_for`).
- **Identifier quoting:** table/column names are quoted per-dialect (`"..."` for PG, backticks for
  MySQL) to avoid breakage on reserved-word table names (`_quote_ident`).
- **Type simplification:** added a MySQL type map (`tinyint`→int, `varchar`→text, `datetime`→date,
  etc.) mirroring the existing PG map, so dropdown columns show the same simplified types as before.
- **Engine leak on delete:** `delete_connection` now disposes + removes the cached engine so a
  deleted connection cannot keep a stale pool alive.
