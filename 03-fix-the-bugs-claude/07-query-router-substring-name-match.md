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
