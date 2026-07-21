"""Apply SQL migrations from db/migrations/."""

import asyncio
import re
import sys
from pathlib import Path

from sqlalchemy import text

from db.session import engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _split_sql(sql: str) -> list[str]:
    sql = re.sub(r"--[^\n]*", "", sql)
    parts = re.split(r";\s*", sql)
    return [p.strip() for p in parts if p.strip()]


async def apply_migration(name: str) -> None:
    path = MIGRATIONS_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    statements = _split_sql(path.read_text(encoding="utf-8"))
    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    print(f"Applied {name} ({len(statements)} statements)")


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "002_manager_registries.sql"
    await apply_migration(target)


if __name__ == "__main__":
    asyncio.run(main())
