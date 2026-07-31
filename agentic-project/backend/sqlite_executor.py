"""SQL validation and execution against a user's personal SQLite file.

Reuses the same SELECT-only guard as sql_executor.py (validate_sql is pure
string validation, not tied to Postgres) — personal-dataset queries get the
exact same safety net as global-registry ones.
"""

import logging
import sqlite3

from sql_executor import validate_sql, _infer_column_types

logger = logging.getLogger(__name__)


async def execute_sql(db_path: str, sql: str) -> dict:
    """Execute a validated SELECT query against the given SQLite file."""
    validated = validate_sql(sql)
    logger.info("Executing SQLite query on %s: %s", db_path, validated[:200])
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(validated)
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []
        data = [dict(row) for row in rows]
    finally:
        conn.close()
    column_types = _infer_column_types(columns, data)
    return {
        "sql": validated,
        "columns": columns,
        "column_types": column_types,
        "rows": data,
        "row_count": len(data),
    }


async def explain_sql(db_path: str, sql: str) -> list[str]:
    """Run EXPLAIN QUERY PLAN to validate SQL syntax against the given SQLite file."""
    validated = validate_sql(sql)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.execute(f"EXPLAIN QUERY PLAN {validated}")
        return [str(r[0]) for r in cursor.fetchall()]
    finally:
        conn.close()
