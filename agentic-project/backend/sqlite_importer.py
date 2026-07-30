"""Import a validated CSV (see csv_validator.py) into a user's personal SQLite file.

One SQLite file per user (`{user_data_dir}/{user_id}/data.db`), one table per
uploaded CSV. Re-uploading a file with the same table name replaces it.
"""

import os
import sqlite3

from config import get_settings


import re

def user_db_path(user_id: str) -> str:
    if not re.match(r'^[a-zA-Z0-9_.-]+$', user_id):
        raise ValueError(f"Invalid user_id: {user_id}")
    settings = get_settings()
    d = os.path.join(settings.user_data_dir, user_id)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "data.db")


def import_csv_to_sqlite(
    user_id: str,
    table_name: str,
    columns: list[str],
    column_types: list[str],
    rows: list[dict],
) -> dict:
    """Creates/replaces `table_name` in the user's SQLite file and bulk-inserts rows."""
    db_path = user_db_path(user_id)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        col_defs = ", ".join(f'"{c}" {t}' for c, t in zip(columns, column_types))
        conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

        placeholders = ", ".join("?" for _ in columns)
        col_list = ", ".join(f'"{c}"' for c in columns)
        insert_sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'
        conn.executemany(insert_sql, [tuple(r.get(c) for c in columns) for r in rows])
        conn.commit()
    finally:
        conn.close()
    return {"db_path": db_path, "table_name": table_name, "row_count": len(rows)}


def drop_user_table(user_id: str, table_name: str) -> None:
    db_path = user_db_path(user_id)
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        conn.commit()
    finally:
        conn.close()
