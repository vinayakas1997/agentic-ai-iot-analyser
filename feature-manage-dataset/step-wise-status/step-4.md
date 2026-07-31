# Step 4 — Backend: query routing to external DBs (no data mixing)

> Status: DONE

## What was done

1. **New `backend/query_router.py`** —
   - `_split_backends(datasets_data)` classifies each dataset's table into one of three backends:
     personal SQLite (`sqlite_path`), external connection (`connection_id`), main Postgres.
   - `route_execute(datasets_data, sql)` — validates SQL, detects which table(s) the query
     references (regex word-boundary match, same pattern as the old SQLite routing), and executes
     on the owning backend via `sqlite_executor.execute_sql` / `db_connections.execute_sql_on` /
     `sql_executor.execute_sql`.
   - `route_explain(datasets_data, sql)` — same routing for the critic's EXPLAIN syntax check.
   - **Safety:** if a query references tables from more than one backend, it is REJECTED with a
     clear error ("data is not mixed across databases"). This enforces the no-intermixing decision
     even if the LLM violates the prompt rule.

2. **Replaced the duplicated inline routing** at all execution sites:
   - `/execute-query` critic-approved execution (`api.py`) — was: ad-hoc `sqlite_tables` check.
   - `/execute-query` last-resort execution.
   - DIRECT handler execution.
   - DEEP handler per-aim execution.
   - `focus_agent._run_query_data` — was: separate sqlite-vs-pg logic.

3. **Dataset loading now carries backend info** so the router + prompts know where each table lives:
   - `/execute-query` handler and the `/messages` send_message handler now read
     `source_config.connection_id` / `db_type` and tag `backend` (`external` vs `pg`).

4. **`_fetch_sample_rows`** now routes to the external connection (dialect-aware quoted table name).

5. Added `explain_sql_on()` to `db_connections.py` and `explain_sql()` to `sqlite_executor.py`
   so EXPLAIN works per-backend.

## Test results

- `python3 -m py_compile` on all touched modules → **pass**.
- Cleaned unused imports in `api.py` and `focus_agent.py` (old sqlite/pg inline routing).

## Bugs fixed while building

- **Critic EXPLAIN would reject all external queries:** the critic ran `EXPLAIN` against the main
  Postgres, which doesn't have the external table → every external query would fail validation.
  Fixed by routing EXPLAIN to the owning backend (`route_explain`).
- **Double-quote vs backtick quoting:** sample-row SELECT used `"table"` which is invalid MySQL.
  Fixed with a public `quote_ident(conn, ident)` helper (backticks for MySQL, double-quotes for PG).
- **Bad edit merged two import lines** in api.py during cleanup — caught and fixed immediately.
