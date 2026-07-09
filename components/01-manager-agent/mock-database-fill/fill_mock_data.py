"""Standalone script to fill mock Japan scenario data into the PostgreSQL database.

Usage (from the project root):

    python mock-database-fill/fill_mock_data.py

Requires the database to be running and accessible.
Reads DB_URL from environment, or defaults to local Docker.
"""

import asyncio
import csv
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATA_DIR = Path(__file__).resolve().parent
FALLBACK_DB_URL = os.environ.get(
    "DB_URL",
    "postgresql+asyncpg://manager_agent:manager_agent_pass@localhost:5432/manager_agent_db",
)

LINE_NAME = "JAPAN_SCENARIOS"
PRIMARY = "japan_fruit_sales"
SECONDARY = "japan_fruit_inventory"
TERTIARY = "japan_supplier_quality"

SALES_COLUMNS = [
    {"name": "sale_id", "meaning": "unique sale identifier", "datatype": "serial", "format": None, "nullable": False},
    {"name": "sale_date", "meaning": "date of sale", "datatype": "date", "format": "YYYY-MM-DD", "nullable": False},
    {"name": "prefecture", "meaning": "Japanese prefecture", "datatype": "text", "format": None, "nullable": False},
    {"name": "city", "meaning": "city within prefecture", "datatype": "text", "format": None, "nullable": True},
    {"name": "fruit_name", "meaning": "fruit name in English", "datatype": "text", "format": None, "nullable": False},
    {"name": "variety", "meaning": "Japanese fruit variety", "datatype": "text", "format": None, "nullable": True},
    {"name": "quantity_kg", "meaning": "quantity sold in kilograms", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "price_per_kg_yen", "meaning": "price per kilogram in JPY", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "total_yen", "meaning": "total sale amount in JPY", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "store_type", "meaning": "type of retail store", "datatype": "text", "format": None, "nullable": True},
    {"name": "season", "meaning": "season of sale", "datatype": "text", "format": None, "nullable": True},
    {"name": "festival_season", "meaning": "whether sold during a festival period", "datatype": "boolean", "format": None, "nullable": True},
]

INVENTORY_COLUMNS = [
    {"name": "inventory_id", "meaning": "unique inventory identifier", "datatype": "serial", "format": None, "nullable": False},
    {"name": "inventory_date", "meaning": "date of inventory record", "datatype": "date", "format": "YYYY-MM-DD", "nullable": False},
    {"name": "prefecture", "meaning": "Japanese prefecture", "datatype": "text", "format": None, "nullable": False},
    {"name": "fruit_name", "meaning": "fruit name in English", "datatype": "text", "format": None, "nullable": False},
    {"name": "variety", "meaning": "Japanese fruit variety", "datatype": "text", "format": None, "nullable": True},
    {"name": "warehouse_id", "meaning": "warehouse code", "datatype": "text", "format": None, "nullable": True},
    {"name": "warehouse_city", "meaning": "city where warehouse is located", "datatype": "text", "format": None, "nullable": True},
    {"name": "stock_quantity_kg", "meaning": "current stock in kg", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "reorder_level_kg", "meaning": "minimum stock before reorder", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "supplier_id", "meaning": "supplier identifier", "datatype": "text", "format": None, "nullable": True},
    {"name": "supplier_name", "meaning": "supplier company name", "datatype": "text", "format": None, "nullable": True},
    {"name": "lead_time_days", "meaning": "days from order to delivery", "datatype": "int", "format": None, "nullable": True},
    {"name": "storage_cost_yen_per_kg", "meaning": "daily storage cost per kg in JPY", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "cold_storage", "meaning": "whether requires refrigeration", "datatype": "boolean", "format": None, "nullable": True},
]

QUALITY_COLUMNS = [
    {"name": "supplier_id", "meaning": "unique supplier code", "datatype": "text", "format": None, "nullable": False},
    {"name": "supplier_name", "meaning": "supplier company name", "datatype": "text", "format": None, "nullable": False},
    {"name": "prefecture", "meaning": "prefecture of supplier farm", "datatype": "text", "format": None, "nullable": True},
    {"name": "fruit_name", "meaning": "primary fruit supplied", "datatype": "text", "format": None, "nullable": True},
    {"name": "certification_type", "meaning": "quality certification held", "datatype": "text", "format": None, "nullable": True},
    {"name": "quality_score_2025", "meaning": "quality score out of 100 for 2025", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "quality_score_2026", "meaning": "quality score out of 100 for 2026", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "delivery_on_time_pct", "meaning": "on-time delivery percentage", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "contract_price_yen_per_kg", "meaning": "contract price per kg in JPY", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "farm_size_hectares", "meaning": "size of farm in hectares", "datatype": "numeric", "format": None, "nullable": True},
    {"name": "organic_certified", "meaning": "whether JAS organic certified", "datatype": "boolean", "format": None, "nullable": True},
    {"name": "established_year", "meaning": "year the farm was established", "datatype": "int", "format": None, "nullable": True},
    {"name": "notes", "meaning": "additional notes", "datatype": "text", "format": None, "nullable": True},
]


CREATE_SALES_DDL = """
    CREATE TABLE IF NOT EXISTS japan_fruit_sales (
        sale_id         SERIAL PRIMARY KEY,
        sale_date       DATE NOT NULL,
        prefecture      TEXT NOT NULL,
        city            TEXT,
        fruit_name      TEXT NOT NULL,
        variety         TEXT,
        quantity_kg     NUMERIC(8, 2),
        price_per_kg_yen NUMERIC(8, 2),
        total_yen       NUMERIC(10, 2),
        store_type      TEXT,
        season          TEXT,
        festival_season BOOLEAN DEFAULT FALSE
    );
"""

CREATE_INVENTORY_DDL = """
    CREATE TABLE IF NOT EXISTS japan_fruit_inventory (
        inventory_id         SERIAL PRIMARY KEY,
        inventory_date       DATE NOT NULL,
        prefecture           TEXT NOT NULL,
        fruit_name           TEXT NOT NULL,
        variety              TEXT,
        warehouse_id         TEXT,
        warehouse_city       TEXT,
        stock_quantity_kg    NUMERIC(8, 2),
        reorder_level_kg     NUMERIC(8, 2),
        supplier_id          TEXT,
        supplier_name        TEXT,
        lead_time_days       INT,
        storage_cost_yen_per_kg NUMERIC(6, 2),
        cold_storage         BOOLEAN DEFAULT FALSE
    );
"""

CREATE_QUALITY_DDL = """
    CREATE TABLE IF NOT EXISTS japan_supplier_quality (
        supplier_id             TEXT NOT NULL PRIMARY KEY,
        supplier_name           TEXT NOT NULL,
        prefecture              TEXT,
        fruit_name              TEXT,
        certification_type      TEXT,
        quality_score_2025      NUMERIC(4, 1),
        quality_score_2026      NUMERIC(4, 1),
        delivery_on_time_pct    NUMERIC(5, 1),
        contract_price_yen_per_kg NUMERIC(8, 2),
        farm_size_hectares      NUMERIC(6, 1),
        organic_certified       BOOLEAN DEFAULT FALSE,
        established_year        INT,
        notes                   TEXT
    );
"""


def _load_csv(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


async def _ensure_tables(db: AsyncSession) -> None:
    await db.execute(text(CREATE_SALES_DDL))
    await db.execute(text(CREATE_INVENTORY_DDL))
    await db.execute(text(CREATE_QUALITY_DDL))


async def _upsert_registry(
    db: AsyncSession, values: dict, now: datetime
) -> None:
    sql = text("""
        INSERT INTO global_registry (
            line_name, dataset_name, synonyms, description,
            source_type, source_config, column_definitions, role,
            join_hints, suggested_aims, verified, global_version,
            status, maintained_by, updated_at
        ) VALUES (
            :line_name, :dataset_name, CAST(:synonyms AS jsonb), :description,
            :source_type, CAST(:source_config AS jsonb), CAST(:column_definitions AS jsonb), :role,
            CAST(:join_hints AS jsonb), CAST(:suggested_aims AS jsonb), :verified, :global_version,
            :status, :maintained_by, :updated_at
        ) ON CONFLICT (line_name, dataset_name) DO UPDATE SET
            synonyms = EXCLUDED.synonyms,
            description = EXCLUDED.description,
            source_type = EXCLUDED.source_type,
            source_config = EXCLUDED.source_config,
            column_definitions = EXCLUDED.column_definitions,
            role = EXCLUDED.role,
            join_hints = EXCLUDED.join_hints,
            suggested_aims = EXCLUDED.suggested_aims,
            verified = EXCLUDED.verified,
            global_version = EXCLUDED.global_version,
            status = EXCLUDED.status,
            maintained_by = EXCLUDED.maintained_by,
            updated_at = EXCLUDED.updated_at
    """)
    await db.execute(sql, {
        "line_name": values["line_name"],
        "dataset_name": values["dataset_name"],
        "synonyms": json.dumps(values.get("synonyms")),
        "description": values.get("description"),
        "source_type": values["source_type"],
        "source_config": json.dumps(values["source_config"]),
        "column_definitions": json.dumps(values["column_definitions"]),
        "role": values.get("role"),
        "join_hints": json.dumps(values.get("join_hints")),
        "suggested_aims": json.dumps(values.get("suggested_aims")),
        "verified": values["verified"],
        "global_version": values["global_version"],
        "status": values["status"],
        "maintained_by": values.get("maintained_by"),
        "updated_at": now,
    })


def _coerce_sales(row: dict) -> dict:
    return {
        "sale_date": date.fromisoformat(row["sale_date"]),
        "prefecture": row["prefecture"],
        "city": row["city"] or None,
        "fruit_name": row["fruit_name"],
        "variety": row["variety"] or None,
        "quantity_kg": float(row["quantity_kg"]) if row["quantity_kg"] else None,
        "price_per_kg_yen": float(row["price_per_kg_yen"]) if row["price_per_kg_yen"] else None,
        "total_yen": float(row["total_yen"]) if row["total_yen"] else None,
        "store_type": row["store_type"] or None,
        "season": row["season"] or None,
        "festival_season": row["festival_season"].strip().lower() == "true" if row["festival_season"] else False,
    }


def _coerce_inventory(row: dict) -> dict:
    return {
        "inventory_date": date.fromisoformat(row["inventory_date"]),
        "prefecture": row["prefecture"],
        "fruit_name": row["fruit_name"],
        "variety": row["variety"] or None,
        "warehouse_id": row["warehouse_id"] or None,
        "warehouse_city": row["warehouse_city"] or None,
        "stock_quantity_kg": float(row["stock_quantity_kg"]) if row["stock_quantity_kg"] else None,
        "reorder_level_kg": float(row["reorder_level_kg"]) if row["reorder_level_kg"] else None,
        "supplier_id": row["supplier_id"] or None,
        "supplier_name": row["supplier_name"] or None,
        "lead_time_days": int(row["lead_time_days"]) if row["lead_time_days"] else None,
        "storage_cost_yen_per_kg": float(row["storage_cost_yen_per_kg"]) if row["storage_cost_yen_per_kg"] else None,
        "cold_storage": row["cold_storage"].strip().lower() == "true" if row["cold_storage"] else False,
    }


def _coerce_quality(row: dict) -> dict:
    return {
        "supplier_id": row["supplier_id"],
        "supplier_name": row["supplier_name"],
        "prefecture": row["prefecture"] or None,
        "fruit_name": row["fruit_name"] or None,
        "certification_type": row["certification_type"] or None,
        "quality_score_2025": float(row["quality_score_2025"]) if row["quality_score_2025"] else None,
        "quality_score_2026": float(row["quality_score_2026"]) if row["quality_score_2026"] else None,
        "delivery_on_time_pct": float(row["delivery_on_time_pct"]) if row["delivery_on_time_pct"] else None,
        "contract_price_yen_per_kg": float(row["contract_price_yen_per_kg"]) if row["contract_price_yen_per_kg"] else None,
        "farm_size_hectares": float(row["farm_size_hectares"]) if row["farm_size_hectares"] else None,
        "organic_certified": row["organic_certified"].strip().lower() == "true" if row["organic_certified"] else False,
        "established_year": int(row["established_year"]) if row["established_year"] else None,
        "notes": row["notes"] or None,
    }


_COERCERS = {
    "japan_fruit_sales": _coerce_sales,
    "japan_fruit_inventory": _coerce_inventory,
    "japan_supplier_quality": _coerce_quality,
}


async def _truncate_and_insert(db: AsyncSession, table: str, rows: list[dict]) -> int:
    await db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    if not rows:
        return 0
    coerce_fn = _COERCERS[table]
    typed_rows = [coerce_fn(r) for r in rows]
    cols = list(typed_rows[0].keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    col_names = ", ".join(cols)
    stmt = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})")
    for row in typed_rows:
        await db.execute(stmt, row)
    return len(rows)


async def fill(db_url: str | None = None) -> None:
    url = db_url or FALLBACK_DB_URL
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.now(timezone.utc)
    synonyms = ["Japan scenarios", "JAPAN_SCENARIOS", "Japanese fruit data", "japan", "Japan market", "japan fruit", "japan_fruit", "JP_FRUIT", "JAPAN_FRUIT"]

    sales_rows = _load_csv("scenario_1_japan_fruit_sales.csv")
    inv_rows = _load_csv("scenario_2_fruit_inventory_japan.csv")
    qual_rows = _load_csv("scenario_3_supplier_quality_japan.csv")
    pg_url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    async with SessionLocal() as db:
        await _ensure_tables(db)
        sales_count = await _truncate_and_insert(db, "japan_fruit_sales", sales_rows)
        inv_count = await _truncate_and_insert(db, "japan_fruit_inventory", inv_rows)
        qual_count = await _truncate_and_insert(db, "japan_supplier_quality", qual_rows)

        sales_dataset = {
            "line_name": LINE_NAME, "dataset_name": PRIMARY, "synonyms": synonyms,
            "description": "Fruit sales across Japanese prefectures with varieties, prices, and seasonal trends",
            "source_type": "pg",
            "source_config": {"url": pg_url, "schema": "public", "table": PRIMARY},
            "column_definitions": SALES_COLUMNS, "role": "primary",
            "join_hints": {
                "to_dataset": SECONDARY,
                "on": ["prefecture", "fruit_name"],
                "note": "Link sales to inventory by prefecture and fruit",
            },
            "suggested_aims": [
                "total sales by prefecture", "average price per kg by fruit and season",
                "festival season sales impact", "top selling fruits per region",
            ],
            "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
        }

        inv_dataset = {
            "line_name": LINE_NAME, "dataset_name": SECONDARY, "synonyms": synonyms,
            "description": "Fruit warehouse inventory levels and supplier details across Japan",
            "source_type": "pg",
            "source_config": {"url": pg_url, "schema": "public", "table": SECONDARY},
            "column_definitions": INVENTORY_COLUMNS, "role": "secondary",
            "join_hints": {
                "to_dataset": PRIMARY,
                "on": ["prefecture", "fruit_name"],
                "note": "Link inventory to sales by prefecture and fruit",
            },
            "suggested_aims": [
                "stock levels by prefecture and fruit", "supplier lead time analysis",
                "cold storage vs non-cold storage inventory", "reorder risk by fruit",
            ],
            "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
        }

        qual_dataset = {
            "line_name": LINE_NAME, "dataset_name": TERTIARY, "synonyms": synonyms,
            "description": "Supplier quality scores, certifications, and contract terms for Japanese fruit farms",
            "source_type": "pg",
            "source_config": {"url": pg_url, "schema": "public", "table": TERTIARY},
            "column_definitions": QUALITY_COLUMNS, "role": "tertiary",
            "join_hints": [
                {
                    "to_dataset": SECONDARY, "on": ["supplier_id"],
                    "note": "Link supplier quality to inventory supplier records",
                },
                {
                    "to_dataset": PRIMARY, "on": ["prefecture", "fruit_name"],
                    "note": "Link supplier quality to sales by prefecture and fruit",
                },
            ],
            "suggested_aims": [
                "quality score trends by prefecture", "organic vs conventional price comparison",
                "supplier certification distribution", "on-time delivery by fruit type",
            ],
            "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
        }

        await _upsert_registry(db, sales_dataset, now)
        await _upsert_registry(db, inv_dataset, now)
        await _upsert_registry(db, qual_dataset, now)
        await db.commit()

    print(f"Seeded {LINE_NAME}: {sales_count} sales, {inv_count} inventory, {qual_count} quality rows")
    print(f"Datasets registered: {PRIMARY}, {SECONDARY}, {TERTIARY}")
    print("Cross-join ready via prefecture, fruit_name, and supplier_id")
    await engine.dispose()


def main() -> None:
    asyncio.run(fill())


if __name__ == "__main__":
    main()
