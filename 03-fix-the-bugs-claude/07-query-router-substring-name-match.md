# 07 — `query_router._ref_names` matches dataset names as substrings anywhere in the SQL text

**Severity:** Medium
**Status:** fix applied, needs test

## Explanation

`agentic-project/backend/query_router.py`, lines 22-23:

```python
def _ref_names(names, sql):
    return [n for n in names if re.search(rf'\b{re.escape(n)}\b', sql, re.IGNORECASE)]
```

This is used by `route_execute`/`_split_backends` to determine which
attached dataset names are actually referenced by a piece of SQL, in order
to decide whether the query should be routed to the sqlite (personal),
pg (registry), or external backend, and to detect/reject queries that mix
backends. The check is a word-boundary regex search over the *entire* SQL
string after `clean_sql` strips comments — it does not restrict matching to
identifier positions (table/column references). String literals in `WHERE`
clauses, aliases, or other incidental text that happens to equal an
attached dataset/table name will also match.

**Failure scenario (reproducible with a crafted name):** two datasets are
attached, one personal (sqlite) named `orders` and one registry (pg) table
that is queried with a literal string equal to `orders` somewhere in a
`WHERE` clause (e.g. `WHERE category = 'orders'`) even though the query
never references the `orders` table. `_ref_names` will report both `orders`
and the actual registry table as "referenced," and `route_execute` may then
either incorrectly reject the query as touching multiple backends, or pick
the wrong backend to execute against.

## Files touched (to fix)

- `agentic-project/backend/query_router.py` (`_ref_names`, lines 22-23, and
  callers in `_split_backends`/`route_execute`, lines ~26-66)
  - Replace substring/word-boundary matching over raw SQL text with actual
    SQL identifier parsing (e.g. via `sqlglot` or similar, if already a
    dependency, or a regex restricted to `FROM`/`JOIN`/table-reference
    positions) so only genuine table references count, not literals or
    aliases.

## Test plan

1. Attach a personal dataset named `orders` (sqlite) and a registry dataset
   whose real table is different, e.g. `shipments` (pg).
2. Execute a query against `shipments` that includes a string literal
   `'orders'` in a `WHERE` clause, referencing no `orders` table.
   - **Before fix:** router may report both `orders` and `shipments` as
     referenced, incorrectly flag as cross-backend, or pick the wrong
     executor.
   - **After fix:** router correctly identifies only `shipments` as
     referenced and routes to the correct (pg) backend.
3. Add a unit test for `_ref_names`/`_split_backends` with SQL containing
   dataset-name-like string literals to lock in correct behavior.

## Current status

Fix applied in `agentic-project/backend/query_router.py`: added
`_TABLE_REF_RE` (matches identifiers immediately after `FROM`/`JOIN`,
including comma-joined lists) and `_table_refs()`, and rewrote `_ref_names`
to check membership against that identifier-position set instead of a
word-boundary substring search over the whole query. Manually verified
with a quick script: `SELECT * FROM shipments WHERE category = 'orders'`
now correctly reports only `shipments` as referenced (previously would
have also flagged `orders`); `FROM orders JOIN shipments ...` and `FROM
orders, shipments` both still correctly report both tables. This is a
lightweight regex-based identifier parser, not a full SQL parser — still
needs the unit test noted in the test plan and a check against real
generated-SQL shapes from `generate_sql`/`generate_sql_data` for edge cases
(e.g. CTEs, subqueries) not covered by the quick manual check.

## Regression found in this fix (fixed 2026-08-04)

The original `_TABLE_REF_RE` restricted identifiers to `[a-zA-Z_]\w*`,
which silently broke routing for **non-ASCII (e.g. Japanese) table names**:
Python's `\b`/`\w` are unicode-aware, so the previous `\b{name}\b` matched
`FROM 生産情報_2026_07_10` fine, but the new ASCII-only token matcher could
not. `_ref_names()` then returned `[]` for every backend, `route_execute`
fell through to the main shared Postgres, and any query against a Japanese
table failed with `asyncpg.UndefinedTableError: relation "生産…" does not
exist` — surfaced to the agent as a truncated `SQL execution failed:
(sqlalchemy.dialects.postgresql.asyncp…`, which the template/FOCUS agents
retried until their round budget (16/12) was exhausted and they reported
"no data".

Fix (same commit): `_TABLE_REF_RE` now captures identifier tokens
permissively (up to whitespace/comma/paren, quoted names supported) and
`_norm_table_ref()` strips surrounding double quotes and any schema prefix
(`public.x` → `x`). The bug-07 literal case is preserved: a string literal
such as `WHERE category = 'orders'` still does not match, because the
regex only inspects table-reference position. Verified:

- `SELECT COUNT(*) FROM 生産実績_01` (exists in user SQLite) → now routes to
  SQLite and returns data (previously fell through to Postgres and errored).
- The user's failing template run on `生産情報_2026_07_10` now completes:
  `route=template`, `done=True`, 2 query results returned with real rows.
- Added a defensive guard in `route_execute`/`route_explain`: if datasets
  are attached but **zero** referenced tables resolve, it raises a clear
  "table not present among the attached datasets" error instead of falling
  through to the shared Postgres — so a name mismatch can never silently
  burn the full agent round budget again.

Note: the `生産情報_2026_07_0X` datasets themselves had also lost their data
tables (registry rows were `active` but the SQLite file predated the
upload); they were re-uploaded from `prod-info-test-files-5-days/` and all
five now query correctly.
