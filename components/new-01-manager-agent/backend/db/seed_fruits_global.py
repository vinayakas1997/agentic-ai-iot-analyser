"""Seed global_registry with FRUITS_TEST datasets (fruits + fruit_quality)."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from config import get_settings
from db.models import GlobalRegistry
from db.session import AsyncSessionLocal

LINE_NAME = "FRUITS_TEST"
PRIMARY_DATASET = "fruits"
SECONDARY_DATASET = "fruit_quality"

FRUITS_COLUMNS = [
    {"name": "sale_date", "meaning": "date of sale", "datatype": "date", "format": "YYYY-MM-DD", "nullable": False},
    {"name": "sale_time", "meaning": "time of sale", "datatype": "time", "format": "HH:MM:SS", "nullable": False},
    {"name": "fruits_id", "meaning": "fruit product id", "datatype": "int", "format": None, "nullable": False},
    {"name": "fruits_name", "meaning": "fruit name", "datatype": "text", "format": None, "nullable": False},
    {"name": "cost", "meaning": "unit cost", "datatype": "numeric", "format": None, "nullable": False},
    {"name": "quantity", "meaning": "quantity sold", "datatype": "int", "format": None, "nullable": False},
    {"name": "store_id", "meaning": "store identifier", "datatype": "text", "format": None, "nullable": True},
    {"name": "category", "meaning": "fruit category", "datatype": "text", "format": None, "nullable": True},
    {"name": "supplier", "meaning": "supplier name", "datatype": "text", "format": None, "nullable": True},
    {"name": "unit", "meaning": "unit of measure", "datatype": "text", "format": None, "nullable": True},
    {"name": "discount_pct", "meaning": "discount percentage", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "tax", "meaning": "tax amount", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "total", "meaning": "total sale amount", "datatype": "numeric", "format": None, "nullable": False},
    {"name": "region", "meaning": "sales region", "datatype": "text", "format": None, "nullable": True},
    {"name": "country", "meaning": "country", "datatype": "text", "format": None, "nullable": True},
    {"name": "organic", "meaning": "organic flag", "datatype": "boolean", "format": None, "nullable": True},
    {"name": "batch_id", "meaning": "batch identifier", "datatype": "text", "format": None, "nullable": True},
    {"name": "shelf_life_days", "meaning": "shelf life in days", "datatype": "int", "format": None, "nullable": True},
    {"name": "warehouse", "meaning": "warehouse code", "datatype": "text", "format": None, "nullable": True},
    {"name": "notes", "meaning": "optional notes", "datatype": "text", "format": None, "nullable": True},
]

QUALITY_COLUMNS = [
    {"name": "batch_id", "meaning": "batch identifier", "datatype": "text", "format": None, "nullable": False},
    {"name": "inspection_date", "meaning": "inspection date", "datatype": "date", "format": "YYYY-MM-DD", "nullable": True},
    {"name": "defect_rate", "meaning": "defect rate percentage", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "quality_grade", "meaning": "quality grade A/B/C", "datatype": "text", "format": None, "nullable": True},
    {"name": "inspector_id", "meaning": "inspector identifier", "datatype": "text", "format": None, "nullable": True},
    {"name": "temperature_c", "meaning": "storage temperature Celsius", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "humidity_pct", "meaning": "storage humidity percent", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "notes", "meaning": "inspection notes", "datatype": "text", "format": None, "nullable": True},
]


def _pg_url_from_settings() -> str:
    return get_settings().db_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _upsert_dataset(db, values: dict, now: datetime) -> None:
    stmt = insert(GlobalRegistry).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["line_name", "dataset_name"],
        set_={
            "synonyms": values.get("synonyms"),
            "description": values["description"],
            "source_type": values["source_type"],
            "source_config": values["source_config"],
            "column_definitions": values["column_definitions"],
            "role": values["role"],
            "join_hints": values["join_hints"],
            "suggested_aims": values["suggested_aims"],
            "data_earliest_ts": values.get("data_earliest_ts"),
            "verified": values["verified"],
            "global_version": values["global_version"],
            "status": values["status"],
            "maintained_by": values["maintained_by"],
            "updated_at": now,
        },
    )
    await db.execute(stmt)


async def seed() -> None:
    now = datetime.now(timezone.utc)
    pg_url = _pg_url_from_settings()
    synonyms = ["Vinayaka", "Vinayaka fruits", "FRUITS_TEST", "fruits test"]

    primary = {
        "line_name": LINE_NAME,
        "dataset_name": PRIMARY_DATASET,
        "synonyms": synonyms,
        "description": "Test fruits sales dataset",
        "source_type": "pg",
        "source_config": {"url": pg_url, "schema": "public", "table": "test_fruits"},
        "column_definitions": FRUITS_COLUMNS,
        "role": "primary",
        "join_hints": None,
        "suggested_aims": ["average cost by fruit", "sales by region"],
        "verified": True,
        "global_version": 1,
        "status": "active",
        "maintained_by": "iot_test",
    }

    secondary = {
        "line_name": LINE_NAME,
        "dataset_name": SECONDARY_DATASET,
        "synonyms": synonyms,
        "description": "Fruit batch quality inspections",
        "source_type": "pg",
        "source_config": {"url": pg_url, "schema": "public", "table": "test_fruit_quality"},
        "column_definitions": QUALITY_COLUMNS,
        "role": "secondary",
        "join_hints": {
            "to_dataset": PRIMARY_DATASET,
            "on": ["batch_id"],
            "note": "Link quality inspections to sales batches",
        },
        "suggested_aims": [
            "defect rate by quality grade",
            "average defect rate by batch",
        ],
        "verified": True,
        "global_version": 1,
        "status": "active",
        "maintained_by": "iot_test",
    }

    async with AsyncSessionLocal() as db:
        await _upsert_dataset(db, primary, now)
        await _upsert_dataset(db, secondary, now)
        fruits_rows = (await db.execute(text("SELECT COUNT(*) FROM test_fruits"))).scalar_one()
        quality_rows = (
            await db.execute(text("SELECT COUNT(*) FROM test_fruit_quality"))
        ).scalar_one()

        date_cols = {"test_fruits": "sale_date", "test_fruit_quality": "inspection_date"}
        for table, dataset in [("test_fruits", "fruits"), ("test_fruit_quality", "fruit_quality")]:
            result = await db.execute(
                text(f"SELECT MIN({date_cols[table]}) FROM {table}")
            )
            min_date = result.scalar_one_or_none()
            if min_date:
                await db.execute(
                    text("UPDATE global_registry SET data_earliest_ts = :ts WHERE line_name = :line AND dataset_name = :ds"),
                    {"ts": min_date, "line": LINE_NAME, "ds": dataset},
                )

        await db.commit()

    print(f"Seeded global_registry: {LINE_NAME} datasets={PRIMARY_DATASET}, {SECONDARY_DATASET}")
    print(f"test_fruits rows: {fruits_rows}, test_fruit_quality rows: {quality_rows}")
    print("synonyms include 'Vinayaka'")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
