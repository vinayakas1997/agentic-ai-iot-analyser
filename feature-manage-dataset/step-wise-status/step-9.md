# Step 9 — Rebuild backend + frontend, verify end-to-end

> Status: DONE

## What was done

1. **Dockerfile fix:** `python:3.12-slim` lacked the C build toolchain for `asyncmy`
   (missing `stdlib.h`). Added `build-essential` to the apt-get install line.
2. Rebuilt backend with the new dependency: `docker compose build --no-cache backend && docker compose up -d backend`.
3. init_db ran on startup → `db_connections` table created (confirmed via `\dt`).
4. Rebuilt + restarted frontend: `docker compose build frontend && docker compose up -d frontend`.

## Test results (live, against running stack)

| Check | Result |
|-------|--------|
| Login as IoT user | OK (`{"role":"iot"}`) |
| `GET /api/v2/db-connections` (empty) | OK `[]` |
| `POST /api/v2/db-connections` (Postgres → main DB) | OK `{"id":1}` |
| `POST /api/v2/db-connections/1/test` | OK reachable, `latency_ms:16` |
| `GET /api/v2/db-connections/1/tables` | OK 11 tables returned |
| `POST /api/v2/registry-admin/introspect` with `connection_id` | OK columns + LLM-drafted meanings |
| **Earliest-ts auto-detection** (temp table with 3 timestamps) | OK `2023-06-01T12:00:00` from column `ts` |
| Register + activate external dataset | OK, entry stored with `connection_id`, `db_type`, `data_earliest_ts` |
| AI query against external connection (`/execute-query`) | OK — `MIN(ts)` executed against connection, correct result |
| **No-data-mixing rejection** (`route_execute` unit check) | OK — external+main join rejected; external-only query executes |
| Frontend serving | HTTP 200 on :7008 |
| Backend logs | No errors/exceptions after all tests |

## Bugs fixed during verification

- **`asyncmy` failed to build on `python:3.12-slim`** — missing build-essential (`stdlib.h` not found).
  Fixed in `backend/Dockerfile` by adding `build-essential`.
- **Test data cleanup** — removed the temp `conn_test` table, registry entry, and test connection
  after verification so the environment is clean.

## Remaining manual steps for the user

- Log in as an IoT user → Manage Datasets page now shows the two-panel layout.
- Add a real MySQL/Postgres connection (left panel) → it live-tests automatically.
- Right panel: select the connection → type to filter tables → pick one → "Load table details" →
  verify columns + start date → fill fields → Save & activate.
- In the dashboard, ask the AI a question about a registered external dataset — it will query that
  connection live. (Note: the sample mock tables in this deployment are empty, so queries against
  them return 0 rows; data_earliest_ts will also be empty for empty tables.)
