"""External database connection management for the IoT registry team.

Handles CRUD for `db_connections`, live reachability testing, table listing,
table introspection (columns + sample rows + earliest timestamp), and live
read-only SQL execution against PostgreSQL or MySQL connections.

Connection engines are cached per connection id; deleted connections dispose
their engine.
"""

import logging
import time
import urllib.parse
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy import select, delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from db.models import DbConnection
from db.session import AsyncSessionLocal
from sql_executor import validate_sql

logger = logging.getLogger(__name__)

DEFAULT_PG_SCHEMA = "public"

_engines: dict[int, AsyncEngine] = {}


class ConnectionNotFoundError(ValueError):
    pass


class TableNotFoundError(ValueError):
    pass


# ── serialization / type mapping ──────────────────────────────────────────

_PG_TYPE_MAP = {
    "integer": "int", "bigint": "int", "smallint": "int",
    "double precision": "numeric", "real": "numeric", "numeric": "numeric",
    "boolean": "boolean",
    "date": "date",
    "time": "time", "time without time zone": "time", "time with time zone": "time",
    "timestamp": "date", "timestamp without time zone": "date", "timestamp with time zone": "date",
}

_MYSQL_TYPE_MAP = {
    "tinyint": "int", "smallint": "int", "mediumint": "int", "int": "int", "integer": "int", "bigint": "int",
    "float": "numeric", "double": "numeric", "decimal": "numeric", "numeric": "numeric",
    "bit": "boolean", "bool": "boolean", "boolean": "boolean",
    "date": "date",
    "time": "time",
    "datetime": "date", "timestamp": "date",
}


def _simplify_pg_type(pg_type: str) -> str:
    return _PG_TYPE_MAP.get(pg_type, "text")


def _simplify_mysql_type(mysql_type: str) -> str:
    base = mysql_type.lower().split("(")[0].strip()
    return _MYSQL_TYPE_MAP.get(base, "text")


def _simplify_type(conn: DbConnection, raw_type: str) -> str:
    return _simplify_mysql_type(raw_type) if conn.db_type == "mysql" else _simplify_pg_type(raw_type)


def _serialize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            v = float(v)
        out[k] = v
    return out


def _to_dict(conn: DbConnection) -> dict:
    return {
        "id": conn.id,
        "name": conn.name,
        "db_type": conn.db_type,
        "host": conn.host,
        "port": conn.port,
        "database_name": conn.database_name,
        "username": conn.username,
        "password": conn.password,
        "schema_name": conn.schema_name or (DEFAULT_PG_SCHEMA if conn.db_type == "postgres" else conn.database_name),
        "created_by": conn.created_by,
        "created_at": conn.created_at.isoformat() if conn.created_at else None,
    }


# ── CRUD ──────────────────────────────────────────────────────────────────

async def create_connection(
    name: str,
    db_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    schema_name: str | None = None,
    created_by: str | None = None,
) -> int:
    async with AsyncSessionLocal() as db:
        row = DbConnection(
            name=name.strip(),
            db_type=db_type,
            host=host.strip(),
            port=port,
            database_name=database_name.strip(),
            username=username.strip(),
            password=password,
            schema_name=schema_name.strip() if schema_name and schema_name.strip() else None,
            created_by=created_by.strip() if created_by and created_by.strip() else None,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row.id


async def get_connection(connection_id: int) -> DbConnection:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(DbConnection).where(DbConnection.id == connection_id)
        )).scalar_one_or_none()
    if not row:
        raise ConnectionNotFoundError(f"Connection {connection_id} not found")
    return row


async def list_connections() -> list[dict]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(DbConnection).order_by(DbConnection.created_at.desc())
        )).scalars().all()
    return [_to_dict(r) for r in rows]


async def delete_connection(connection_id: int) -> None:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(DbConnection).where(DbConnection.id == connection_id)
        )).scalar_one_or_none()
        if not row:
            raise ConnectionNotFoundError(f"Connection {connection_id} not found")
        await db.execute(delete(DbConnection).where(DbConnection.id == connection_id))
        await db.commit()
    engine = _engines.pop(connection_id, None)
    if engine is not None:
        await engine.dispose()


# ── engine / DSN ──────────────────────────────────────────────────────────

def _dsn(conn: DbConnection) -> str:
    user = urllib.parse.quote_plus(conn.username)
    pwd = urllib.parse.quote_plus(conn.password)
    if conn.db_type == "mysql":
        return f"mysql+asyncmy://{user}:{pwd}@{conn.host}:{conn.port}/{conn.database_name}"
    return f"postgresql+asyncpg://{user}:{pwd}@{conn.host}:{conn.port}/{conn.database_name}"


def build_engine(conn: DbConnection) -> AsyncEngine:
    engine = _engines.get(conn.id)
    if engine is None:
        dsn = _dsn(conn)
        parsed = make_url(dsn)
        connect_args = {"timeout": 5} if conn.db_type == "postgres" else {"connect_timeout": 5}
        engine = create_async_engine(
            dsn,
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        _engines[conn.id] = engine
    return engine


def _schema_for(conn: DbConnection) -> str:
    return conn.schema_name or (DEFAULT_PG_SCHEMA if conn.db_type == "postgres" else conn.database_name)


def quote_ident(conn: DbConnection, ident: str) -> str:
    if conn.db_type == "mysql":
        return "`" + ident.replace("`", "``") + "`"
    return '"' + ident.replace('"', '""') + '"'


# ── live test ─────────────────────────────────────────────────────────────

async def test_connection(conn: DbConnection) -> dict:
    engine = build_engine(conn)
    start = time.monotonic()
    try:
        async with engine.connect() as c:
            await c.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception as e:
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"ok": False, "latency_ms": latency_ms, "error": str(e)[:300]}


# ── introspection ─────────────────────────────────────────────────────────

async def list_tables(conn: DbConnection) -> list[str]:
    """List table names visible in the connection's schema (for the dropdown)."""
    schema = _schema_for(conn)
    engine = build_engine(conn)
    if conn.db_type == "mysql":
        stmt = text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :s AND table_type IN ('BASE TABLE', 'VIEW') ORDER BY table_name"
        )
    else:
        stmt = text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :s AND table_type IN ('BASE TABLE', 'VIEW') ORDER BY table_name"
        )
    try:
        async with engine.connect() as c:
            result = await c.execute(stmt, {"s": schema})
            return [r[0] for r in result.fetchall()]
    except Exception as e:
        logger.warning("list_tables failed for connection %s: %s", conn.id, e)
        raise


async def introspect_table(conn: DbConnection, table_name: str) -> dict:
    """Return {table_name, columns, sample_rows, data_earliest_ts, data_earliest_col}."""
    schema = _schema_for(conn)
    engine = build_engine(conn)
    if conn.db_type == "mysql":
        col_stmt = text(
            "SELECT column_name, data_type, ordinal_position FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t ORDER BY ordinal_position"
        )
    else:
        col_stmt = text(
            "SELECT column_name, data_type, ordinal_position FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t ORDER BY ordinal_position"
        )
    try:
        async with engine.connect() as c:
            col_rows = (await c.execute(col_stmt, {"s": schema, "t": table_name})).all()
            if not col_rows:
                raise TableNotFoundError(f"Table '{table_name}' does not exist in schema '{schema}'")
            columns = [{"name": r[0], "datatype": _simplify_type(conn, r[1])} for r in col_rows]
            quoted = quote_ident(conn, table_name)
            sample = (await c.execute(text(f"SELECT * FROM {quoted} LIMIT 5"))).mappings().all()
            sample_rows = [_serialize_row(dict(r)) for r in sample]

            data_earliest_ts = None
            data_earliest_col = None
            for col in columns:
                if col["datatype"] != "date":
                    continue
                try:
                    min_row = (await c.execute(
                        text(f"SELECT MIN({quote_ident(conn, col['name'])}) AS m FROM {quoted}")
                    )).mappings().first()
                    val = min_row["m"] if min_row else None
                except Exception:
                    val = None
                if val is None:
                    continue
                iso = val.isoformat() if isinstance(val, (datetime, date)) else str(val)
                if data_earliest_ts is None or iso < data_earliest_ts:
                    data_earliest_ts = iso
                    data_earliest_col = col["name"]
    except TableNotFoundError:
        raise
    except Exception as e:
        logger.warning("introspect_table failed for connection %s: %s", conn.id, e)
        raise TableNotFoundError(f"Table '{table_name}' is not reachable: {str(e)[:200]}")

    return {
        "table_name": table_name,
        "schema": schema,
        "columns": columns,
        "sample_rows": sample_rows,
        "data_earliest_ts": data_earliest_ts,
        "data_earliest_col": data_earliest_col,
    }


# ── live SQL execution ────────────────────────────────────────────────────

async def execute_sql_on(conn: DbConnection, sql: str) -> dict:
    """Validate and execute a read-only SELECT against the connection.
    Same result shape as sql_executor.execute_sql."""
    validated = validate_sql(sql)
    engine = build_engine(conn)
    logger.info("Executing SQL on %s connection %s: %s", conn.db_type, conn.id, validated[:200])
    async with engine.connect() as c:
        result = await c.execute(text(validated))
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
    return {
        "sql": validated,
        "columns": columns,
        "column_types": _infer_column_types(columns, data),
        "rows": data,
        "row_count": len(data),
    }


async def explain_sql_on(conn: DbConnection, sql: str) -> list[str]:
    """Run EXPLAIN to validate SQL syntax against the connection. Returns plan lines."""
    validated = validate_sql(sql)
    engine = build_engine(conn)
    async with engine.connect() as c:
        result = await c.execute(text(f"EXPLAIN {validated}"))
        lines = [r[0] for r in result.fetchall()]
    return lines


def _infer_column_types(columns: list[str], rows: list[dict]) -> list[str]:
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
            break
        type_map.append(detected)
    return type_map
