"""Route SQL execution to whichever backend holds the referenced table(s).

Three backends exist:
- main Postgres (`sql_executor.execute_sql`) — shared global_registry tables without a connection
- external PostgreSQL/MySQL connections (`db_connections.execute_sql_on`)
- personal SQLite files (`sqlite_executor.execute_sql`) — user-uploaded CSVs

A query may reference tables from at most ONE backend — mixing databases is rejected
(the system intentionally does not mix data across databases).
"""

import re
import logging

from sql_executor import validate_sql, execute_sql, explain_sql
import sqlite_executor
from db_connections import get_connection, execute_sql_on, explain_sql_on

logger = logging.getLogger(__name__)


_TABLE_REF_RE = re.compile(
    r'\b(?:FROM|JOIN)\s+([a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)*)',
    re.IGNORECASE,
)


def _table_refs(sql: str) -> set[str]:
    """Identifiers that appear in table-reference position (after FROM/JOIN,
    including comma-joined lists in a FROM clause) — not just anywhere in the SQL
    text. A plain substring/word-boundary search over the whole query would also
    match string literals, aliases, or column names that happen to equal a dataset
    name, which can misroute or falsely reject single-backend queries."""
    refs: set[str] = set()
    for m in _TABLE_REF_RE.finditer(sql):
        for part in m.group(1).split(','):
            refs.add(part.strip())
    return refs


def _ref_names(names, sql):
    refs = _table_refs(sql)
    return [n for n in names if n in refs]


def _split_backends(datasets_data: list[dict]):
    sqlite_tables: dict[str, str] = {}
    main_tables: set[str] = set()
    ext_tables: dict[str, int] = {}
    for d in datasets_data:
        table = d.get("table") or d.get("dataset_name")
        if not table:
            continue
        backend = d.get("backend", "pg")
        if backend == "sqlite" and d.get("sqlite_path"):
            sqlite_tables[table] = d["sqlite_path"]
        elif d.get("connection_id"):
            ext_tables[table] = d["connection_id"]
        else:
            main_tables.add(table)
    return sqlite_tables, main_tables, ext_tables


async def route_execute(datasets_data: list[dict], sql: str) -> dict:
    """Validate then execute `sql` against the backend owning the referenced table(s).
    Raises ValueError when the query mixes tables from different databases."""
    validated = validate_sql(sql)
    sqlite_tables, main_tables, ext_tables = _split_backends(datasets_data)

    ref_sqlite = _ref_names(sqlite_tables, validated)
    ref_main = _ref_names(main_tables, validated)
    ref_ext = _ref_names(ext_tables, validated)

    referenced = sum(bool(x) for x in (ref_sqlite, ref_main, ref_ext))
    if referenced > 1:
        raise ValueError(
            "This query references tables from different databases and cannot be executed as one "
            "query. Please query them separately — data is not mixed across databases."
        )

    if ref_sqlite:
        return await sqlite_executor.execute_sql(sqlite_tables[ref_sqlite[0]], validated)
    if ref_ext:
        conn = await get_connection(ext_tables[ref_ext[0]])
        return await execute_sql_on(conn, validated)
    return await execute_sql(validated)


async def route_explain(datasets_data: list[dict], sql: str) -> list[str]:
    """Run EXPLAIN against the backend owning the referenced table(s) for syntax validation."""
    validated = validate_sql(sql)
    sqlite_tables, main_tables, ext_tables = _split_backends(datasets_data)

    ref_sqlite = _ref_names(sqlite_tables, validated)
    ref_main = _ref_names(main_tables, validated)
    ref_ext = _ref_names(ext_tables, validated)

    referenced = sum(bool(x) for x in (ref_sqlite, ref_main, ref_ext))
    if referenced > 1:
        raise ValueError(
            "This query references tables from different databases and cannot be validated as one "
            "query. Please query them separately — data is not mixed across databases."
        )

    if ref_sqlite:
        return await sqlite_executor.explain_sql(sqlite_tables[ref_sqlite[0]], validated)
    if ref_ext:
        conn = await get_connection(ext_tables[ref_ext[0]])
        return await explain_sql_on(conn, validated)
    return await explain_sql(validated)
