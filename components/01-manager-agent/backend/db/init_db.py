"""Run all migrations in order, then seed test data. Fully idempotent.

Skips 002_manager_registries.sql — it is Phase 1, superceded by
003_manager_tables_fresh.sql (Phase A) which drops and recreates the same
tables with a different schema.
"""

import asyncio
import sys
from pathlib import Path

from db.run_migration import apply_migration
from db.seed_fruits_global import seed as seed_fruits

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

SKIP = {"002_manager_registries.sql"}


async def init_db() -> None:
    all_files = sorted(f.name for f in MIGRATIONS_DIR.iterdir() if f.suffix == ".sql")
    migration_files = [f for f in all_files if f not in SKIP]
    skipped = [f for f in all_files if f in SKIP]
    print(f"Found {len(all_files)} migration(s); applying {len(migration_files)}, skipping {skipped}")

    for name in migration_files:
        try:
            await apply_migration(name)
        except FileNotFoundError as exc:
            print(f"ERROR file not found: {exc}")
            sys.exit(1)

    print("All migrations applied. Seeding test data...")
    await seed_fruits()
    print("init_db complete.")


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
