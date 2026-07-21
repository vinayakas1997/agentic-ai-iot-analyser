"""SQL validation and execution against Postgres."""

import re
import logging
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import text
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

FORBIDDEN_KEYWORDS = [
    r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', r'\bINSERT\b',
    r'\bALTER\b', r'\bTRUNCATE\b', r'\bCREATE\b', r'\bREPLACE\b',
    r'\bEXEC\b', r'\bEXECUTE\b', r'\bCALL\b', r'\bMERGE\b',
]


def clean_sql(raw: str) -> str:
    cleaned = raw.strip()
    block_match = re.search(r'```(?:sql)?\s*\n?(.*?)\n?```', cleaned, re.DOTALL)
    if block_match:
        cleaned = block_match.group(1).strip()
    cleaned = re.sub(r'--.*', '', cleaned)
    cleaned = cleaned.rstrip(';').strip()
    return cleaned


def validate_sql(sql: str) -> str:
    """Validate SQL is a safe read-only query. Returns cleaned SQL."""
    cleaned = clean_sql(sql)
    if not cleaned:
        raise ValueError("Empty SQL after cleaning")

    upper = cleaned.upper()

    if not (upper.startswith('SELECT') or upper.startswith('WITH')):
        raise ValueError("Only SELECT queries are allowed")

    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, upper):
            raise ValueError(f"Forbidden SQL keyword in query")

    if 'LIMIT' not in upper:
        cleaned = cleaned.rstrip(';') + ' LIMIT 200'

    return cleaned


def validate_sql_safety(sql: str) -> list[str]:
    """Returns list of safety issues (empty = safe)."""
    issues = []
    upper = sql.upper()
    if not (upper.startswith('SELECT') or upper.startswith('WITH')):
        issues.append("Only SELECT queries are allowed")
    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, upper):
            issues.append("Forbidden SQL keyword in query")
    if re.search(r'\bCROSS\s+JOIN\b', upper):
        issues.append("CROSS JOIN is not allowed — use INNER/LEFT JOIN with ON")
    if re.search(r'\.\w+\.\w+', sql):
        issues.append("Schema-qualified table names (schema.table) are not allowed")
    if 'LIMIT' not in upper:
        issues.append("Missing LIMIT clause — results may be unbounded")
    return issues


async def explain_sql(sql: str) -> list[str]:
    """Run EXPLAIN to validate SQL syntax. Returns query plan lines."""
    validated = validate_sql(sql)
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(f"EXPLAIN {validated}"))
        lines = [row[0] for row in result.fetchall()]
        await db.rollback()
    return lines


def _infer_column_types(columns: list[str], rows: list[dict]) -> list[str]:
    """Infer column types from actual data values in rows (checks first 10 rows)."""
    type_map = []
    for col in columns:
        detected = "text"
        for row in rows[:10]:
            val = row.get(col)
            if val is None:
                continue
            if isinstance(val, bool):
                detected = "boolean"
            elif isinstance(val, int):
                detected = "integer"
            elif isinstance(val, float):
                detected = "float"
            elif isinstance(val, Decimal):
                detected = "decimal"
            elif isinstance(val, datetime):
                detected = "timestamp"
            elif isinstance(val, date):
                detected = "date"
            elif isinstance(val, str):
                detected = "text"
            # Use first non-None match
            break
        type_map.append(detected)
    return type_map


async def execute_sql(sql: str) -> dict:
    """Execute a validated SELECT query and return results."""
    validated = validate_sql(sql)
    logger.info("Executing SQL: %s", validated[:200])
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(validated))
        rows = result.fetchall()
        columns = list(result.keys())
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                if isinstance(val, Decimal):
                    val = float(val)
                row_dict[col] = val
            data.append(row_dict)
        await db.rollback()
    column_types = _infer_column_types(columns, data)
    return {
        "sql": validated,
        "columns": columns,
        "column_types": column_types,
        "rows": data,
        "row_count": len(data),
    }
