# Plan — Multi-DB Connections & Enhanced Manage Datasets Page

> Status: READY TO IMPLEMENT
> Reference: `discussion.md` in this folder

---

## Overview

Turn the single-column "Manage Datasets" page into a two-panel page:

- **Left panel — "Add new database connections":** register PostgreSQL/MySQL connections (shared across IoT users), with live reachability testing.
- **Right panel — dataset registration:** pick a connection → type-to-filter table dropdown → auto-fetch columns, datatypes, sample rows, earliest date → human fills required global-registry fields → add to global registry.

Plus: extend the SQL execution pipeline so the AI analyser runs real queries **live** against the external DBs. No data mixing across databases.

---

## Implementation Order

### Step 1 — Backend: model + module + dependency

**`backend/db/models.py`** — add `DbConnection` model, table `db_connections`:
`id`, `name`, `db_type` (`postgres` | `mysql`), `host`, `port`, `database_name`, `username`, `password`, `schema` (default `public`, nullable), `created_at`, `updated_at`. Shared — no owner column.

**`backend/db/init_db.py`** — idempotent `CREATE TABLE IF NOT EXISTS db_connections` in the table-creation step.

**`backend/requirements.txt`** — add `asyncmy>=0.2.9` (async MySQL driver for SQLAlchemy).

**New `backend/db_connections.py`** module:
- `create_connection(...)`, `list_connections()`, `delete_connection(id)`
- `build_engine(conn)` — cached SQLAlchemy async engine per connection id (`postgresql+asyncpg://` / `mysql+asyncmy://`) with short connect timeout
- `test_connection(conn)` → `SELECT 1`, returns `{ok, latency_ms, error?}`
- `list_tables(conn)` → PG: `information_schema.tables`; MySQL: same, filtered to schema
- `introspect_table(conn, table)` → columns + datatypes + sample rows (generalized from `registry_admin.introspect_pg_table`) + earliest-timestamp detection (find date/timestamp columns, compute `MIN()` per candidate, return candidate value) → fills `data_earliest_ts`
- `execute_sql_on(conn, sql)` → same result shape as `sql_executor.execute_sql` (columns, column_types, rows, row_count)

### Step 2 — Backend: API routes (`backend/api.py`)

All IoT-role protected via existing `_require_iot_role` + `_require_user_id`:
- `POST /api/v2/db-connections` — create
- `GET /api/v2/db-connections` — list
- `DELETE /api/v2/db-connections/{id}` — delete
- `POST /api/v2/db-connections/{id}/test` — live test
- `GET /api/v2/db-connections/{id}/tables` — dropdown list
- Extend `POST /api/v2/registry-admin/introspect` — accept optional `connection_id` (defaults to main DB, current behavior preserved). Return `columns` (LLM-drafted meanings as today), `sample_rows`, and `data_earliest_ts` candidate.

### Step 3 — Backend: registry persistence (`registry_admin.py`)

- `create_draft_entry()`: store `source_config` as `{"connection_id": <id>, "db_type": <type>, "schema": ..., "table": ...}` for external DBs; keep `{"table": ...}` for main DB.
- Persist `data_earliest_ts` on the `GlobalRegistry` row (field exists, currently unused).
- `list_entries()`: surface `data_earliest_ts` + `source_config` connection info.

### Step 4 — Backend: query execution on external DBs

- New routing helper (e.g. `query_router.py`): `route_execute(datasets_data, sql)` — determine each referenced table's backend (`sqlite_path` / `connection_id` / main) and execute on the right engine. Reuse the existing regex-referenced-table pattern (`api.py:654`).
- Apply routing at the 3 execution sites: `/execute-query` loop (`api.py:643-663`), DEEP handler (`api.py:1536-1541`), `focus_agent.py:195-213`.
- Dataset loading (`api.py:613-620`) must pass through `source_config` → `connection_id` / `db_type` / `schema`.
- **Safety:** reject SQL that references tables from two different backends (prevents cross-DB joins / data mixing).

### Step 5 — Backend: LLM prompts (`aims.py`)

- Tag each dataset in the SQL prompt with its backend: `### <table> [postgres:main]` / `[mysql:<name>]`.
- Add rules: never JOIN tables from different databases; dialect notes (backticks vs double-quotes).

### Step 6 — Frontend: API client (`frontend/src/api/client.ts`)

- Add: `createDbConnection`, `listDbConnections`, `deleteDbConnection`, `testDbConnection`, `listConnectionTables`.
- Extend: `introspectTable` to accept `connection_id`; `createRegistryEntry` to accept `connection_id`.
- Add types: `DbConnection`; extend `RegistryEntry` with `data_earliest_ts`.

### Step 7 — Frontend: two-panel UI (`frontend/src/sections/IotRegistryPage.tsx`)

- Change `max-w-3xl mx-auto` single column → `grid grid-cols-2 gap-6` (left connections / right registration).
- **Left panel:** connection form (name, type select PG/MySQL, host, port, database, username, password, schema) + "Add & Test"; list of saved connections with status badge — "Test" runs live check (green reachable / red unreachable + error + latency); delete button.
- **Right panel:** connection selector → searchable/type-to-filter table dropdown → "Load" → introspection → columns table (editable meanings, as today) → fields: line name, dataset name, description, role, synonyms, start date pre-filled from auto-detected `data_earliest_ts` (overridable) → Save draft / Save & activate (unchanged behavior).
- Keep the "Your entries" list.
- New small filterable-dropdown component reusing existing Tailwind styles.

### Step 8 — Frontend: translations (`frontend/src/lib/translations.ts`)

Add EN + JA keys for: connection panel (add connection, type, host, port, database, username, password, schema, test, reachable, unreachable, latency, delete, saved connections), right-panel labels (connection, table search, start date).

### Step 9 — Rebuild & verify

1. Backend (new dep `asyncmy` + new table): `docker compose build --no-cache backend && docker compose up -d backend`
2. DB reset only if clean schema needed: `docker compose down -v && docker compose up -d`
3. Frontend: `docker compose build frontend && docker compose up -d frontend`
4. Manual test as IoT user:
   - Add a MySQL + Postgres connection → test → both reachable
   - Right panel: pick connection → filter table dropdown → select table → verify columns + start date load
   - Save & activate → entry appears in "Your entries"
   - Ask the chat a question referencing that dataset → verify it queries the correct external backend

---

## Out of Scope (this phase)

- Cross-database JOINs (hard limit — no data mixing).
- Password encryption at rest (documented risk; later hardening).
- Sync/copy of external tables into main DB (only if a future cross-DB-join need emerges).
