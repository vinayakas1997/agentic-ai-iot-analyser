# Discussion Notes — Multi-DB Connections & Enhanced Manage Datasets Page

> Date: 2026-07-31

## Context / Goal

The app has a global registry (`global_registry`) that the **IoT team** maintains. They register the database tables they build/populate, and later **normal users** query them via the AI analyser. Only `status = "active"` entries are visible to normal users (`api.py:835`, `resolve.py:103`).

The current "Manage Datasets" page (`IotRegistryPage.tsx`) is a single-column form:
- User types a table name manually
- Backend introspects that table in the ONE default Postgres DB (`DB_URL`)
- LLM drafts column meanings
- User fills line name / dataset name / description / role / synonyms and saves draft/active

We want to enhance it so the IoT team can work with **multiple real production databases** (their tables live on separate DBs, e.g. MySQL machines), not just the main Postgres.

## Requirements Discussed

### Two-panel page layout

**Left panel — "Add new database connections"**
- Register multiple database connections
- Live testing to check if each connection is reachable (green/red status + latency)
- Manage (list / add / delete)

**Right panel — dataset registration**
- The IoT user types a name → filtered dropdown of available tables
- User picks a table from the chosen connection
- Details required for the global registry are fetched automatically: columns, datatypes, sample rows, start date (`data_earliest_ts`)
- Human fills the required fields and adds the dataset to the global registry

## Decisions Locked

| Topic | Decision |
|-------|----------|
| Connection storage | New `db_connections` table in Postgres (SQLAlchemy model). Survives restarts. |
| DB types supported | PostgreSQL + MySQL (add `asyncmy` async driver) |
| Start date (`data_earliest_ts`) | Auto-detected from the table's timestamp/date column (`MIN()`); user can override |
| Connection scope | Shared across all IoT users (no per-user ownership) |
| Query execution on external DBs | YES — the AI analyser can run real queries against the external connections (live), not just read metadata |
| Data mixing | NO intermixing of data across databases. Each table executes only on its own backend. Cross-database JOINs are forbidden (hard technical limit — you cannot join MySQL and Postgres in one query). Enforced at prompt level AND rejected by the executor. |

## Why live queries (not copying to main DB)

- Real data, always current — the IoT team keeps updating their production tables.
- No sync/ETL pipeline to build or maintain; no staleness.
- Dialects are ~95% identical for the SELECT-only queries the system generates; minor differences handled in the generation prompt, and the existing critic → fix retry loop self-heals runtime errors.
- Matches the existing SQLite personal-dataset routing pattern (`api.py:654`).

**Trade-off accepted:** cross-database JOINs won't work. Analysis must stay within one database per query (per-line databases is fine). If a future need for cross-DB joins emerges, a copy/sync path can be added without reworking the registration UI.

## Existing code touched (references)

- `agentic-project/frontend/src/sections/IotRegistryPage.tsx` — current single-column page
- `agentic-project/backend/registry_admin.py` — `introspect_pg_table()` (single main-DB introspection), draft/confirm/list/delete
- `agentic-project/backend/api.py` — registry-admin routes (`:1011-1063`), SQLite routing pattern (`:654`), DEEP handler routing (`:1536`), dataset loading (`:613`)
- `agentic-project/backend/focus_agent.py` — sqlite-vs-pg routing (`:195-213`)
- `agentic-project/backend/sql_executor.py` — main Postgres executor (`execute_sql`)
- `agentic-project/backend/db/models.py` — `GlobalRegistry` (has unused `data_earliest_ts` at `:25`)
- `agentic-project/backend/config.py` — single `db_url` setting
- `agentic-project/backend/db/init_db.py` — table creation / seeding
- `agentic-project/backend/requirements.txt` — only `asyncpg` currently installed
- `agentic-project/frontend/src/api/client.ts` — API client for registry-admin

## Notes / Risks

- Passwords stored plaintext in the `db_connections` table (internal tool). Encryption could be a later hardening step.
- Existing main-DB entries (`source_config = {"table": ...}`) must keep working unchanged — default path when no connection is chosen.
- Full rebuild needed: backend `--no-cache` (new `asyncmy` dependency + new table), frontend rebuild.
