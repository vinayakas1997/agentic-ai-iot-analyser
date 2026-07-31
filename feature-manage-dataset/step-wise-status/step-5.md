# Step 5 — Backend: LLM prompt backend tags + no-cross-DB rule

> Status: DONE

## What was done

In `backend/aims.py`:

1. **`build_sql_context()`** now appends a `[backend:...]` tag to each `### table` header:
   - External connections → `[<db_type>:<dataset_name>]` (e.g. `[mysql:line_a]`)
   - Personal SQLite → `[personal:sqlite]`
   - Main Postgres → `[postgres:main]`

2. **`SQL_GENERATION_PROMPT` rules** updated:
   - Added: "The `[backend: ...]` tag tells you which database each table lives in. NEVER JOIN or
     reference tables with different backend tags in the same query — they live in separate
     databases and cannot be mixed. Query one database per statement."
   - Changed "Use PostgreSQL syntax" → "Use the dialect of the backend tagged in the headers
     (PostgreSQL for `[postgres:...]`, MySQL for `[mysql:...]`)".

3. **`criticize_sql()`** — EXPLAIN syntax check now goes through `route_explain(datasets_data, sql)`
   instead of the main-DB `explain_sql`, so SQL targeting external tables passes the critic.

## Test results

- `python3 -m py_compile` → **pass**.

## Bugs fixed while building

- The old prompt hardcoded "You are a PostgreSQL query generator / Use PostgreSQL syntax", which
  would have produced invalid MySQL. Now the dialect instruction is per-backend.
- The critic EXPLAIN was the last place that would have silently blocked external-DB queries —
  routed it (see Step 4 note).
