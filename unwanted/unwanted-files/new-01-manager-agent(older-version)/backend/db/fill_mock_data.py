"""Seed the 3 Japan mock-data tables and register them in global_registry.

Relies on SQL migrations 010–012 having already created the tables.
"""

import asyncio
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from config import get_settings
from db.models import GlobalRegistry
from db.session import AsyncSessionLocal

DATA_DIR = Path(__file__).resolve().parent / "mock_data"

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


def _pg_url_from_settings() -> str:
    return get_settings().db_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _load_csv(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


async def _upsert_registry(db, values: dict, now: datetime) -> None:
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


def _convert_row(row: dict, col_defs: list[dict]) -> dict:
    col_map = {c["name"]: c for c in col_defs}
    result = {}
    for key, val in row.items():
        if val is None or val == "":
            result[key] = None
            continue
        dt = col_map.get(key, {}).get("datatype", "text")
        if dt == "date":
            result[key] = date.fromisoformat(val)
        elif dt == "boolean":
            result[key] = str(val).strip().lower() == "true"
        elif dt == "int":
            result[key] = int(val)
        elif dt == "numeric":
            result[key] = Decimal(val)
        else:
            result[key] = val
    return result


async def _truncate_and_insert(db, table: str, rows: list[dict], col_defs: list[dict] | None = None) -> int:
    await db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    col_names = ", ".join(cols)
    stmt = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})")
    for row in rows:
        if col_defs:
            row = _convert_row(row, col_defs)
        await db.execute(stmt, row)
    return len(rows)


async def fill() -> None:
    now = datetime.now(timezone.utc)
    pg_url = _pg_url_from_settings()
    synonyms = ["Japan scenarios", "JAPAN_SCENARIOS", "Japanese fruit data", "japan", "Japan market", "japan fruit", "japan_fruit", "JP_FRUIT", "JAPAN_FRUIT", "vinayaka", "vinayak"]

    sales_rows = _load_csv("scenario_1_japan_fruit_sales.csv")
    inv_rows = _load_csv("scenario_2_fruit_inventory_japan.csv")
    qual_rows = _load_csv("scenario_3_supplier_quality_japan.csv")

    async with AsyncSessionLocal() as db:
        sales_count = await _truncate_and_insert(db, "japan_fruit_sales", sales_rows, SALES_COLUMNS)
        inv_count = await _truncate_and_insert(db, "japan_fruit_inventory", inv_rows, INVENTORY_COLUMNS)
        qual_count = await _truncate_and_insert(db, "japan_supplier_quality", qual_rows, QUALITY_COLUMNS)

        sales_dataset = {
            "line_name": LINE_NAME,
            "dataset_name": PRIMARY,
            "synonyms": synonyms,
            "description": "Fruit sales across Japanese prefectures with varieties, prices, and seasonal trends",
            "source_type": "pg",
            "source_config": {"url": pg_url, "schema": "public", "table": PRIMARY},
            "column_definitions": SALES_COLUMNS,
            "role": "primary",
            "join_hints": {
                "to_dataset": SECONDARY,
                "on": ["prefecture", "fruit_name"],
                "note": "Link sales to inventory by prefecture and fruit",
            },
            "suggested_aims": [
                {"aim": "total sales by prefecture", "description": "Revenue breakdown across Japanese prefectures", "benefits": "Identify top revenue regions for targeted marketing", "columns": [{"dataset": "japan_fruit_sales", "names": ["prefecture", "total_yen"]}]},
                {"aim": "average price per kg by fruit and season", "description": "Seasonal price trends for each fruit variety", "benefits": "Optimize pricing strategy based on seasonal demand", "columns": [{"dataset": "japan_fruit_sales", "names": ["fruit_name", "season", "price_per_kg_yen"]}]},
                {"aim": "inventory turnover vs sales velocity", "description": "Compare how fast inventory moves relative to sales per fruit", "benefits": "Identify slow-moving stock and adjust procurement", "datasets": ["japan_fruit_sales", "japan_fruit_inventory"], "columns": [{"dataset": "japan_fruit_sales", "names": ["prefecture", "fruit_name", "quantity_kg"]}, {"dataset": "japan_fruit_inventory", "names": ["prefecture", "fruit_name", "stock_quantity_kg", "reorder_level_kg"]}]},
                {"aim": "supplier quality impact on sales", "description": "Correlate supplier quality scores with sales performance by region", "benefits": "Prioritize high-quality suppliers to boost revenue", "datasets": ["japan_fruit_sales", "japan_supplier_quality"], "columns": [{"dataset": "japan_fruit_sales", "names": ["prefecture", "fruit_name", "total_yen"]}, {"dataset": "japan_supplier_quality", "names": ["supplier_id", "prefecture", "fruit_name", "quality_score_2025", "quality_score_2026"]}]},
            ],
            "verified": True,
            "global_version": 1,
            "status": "active",
            "maintained_by": "mock_fill",
        }

        inv_dataset = {
            "line_name": LINE_NAME,
            "dataset_name": SECONDARY,
            "synonyms": synonyms,
            "description": "Fruit warehouse inventory levels and supplier details across Japan",
            "source_type": "pg",
            "source_config": {"url": pg_url, "schema": "public", "table": SECONDARY},
            "column_definitions": INVENTORY_COLUMNS,
            "role": "secondary",
            "join_hints": {
                "to_dataset": PRIMARY,
                "on": ["prefecture", "fruit_name"],
                "note": "Link inventory to sales by prefecture and fruit",
            },
            "suggested_aims": [
                {"aim": "stock levels by prefecture and fruit", "description": "Current inventory distribution across warehouses", "benefits": "Prevent stockouts and balance inventory across regions", "columns": [{"dataset": "japan_fruit_inventory", "names": ["prefecture", "fruit_name", "stock_quantity_kg"]}]},
                {"aim": "reorder risk by fruit", "description": "Items approaching reorder threshold by warehouse", "benefits": "Proactive restocking to avoid lost sales", "columns": [{"dataset": "japan_fruit_inventory", "names": ["fruit_name", "stock_quantity_kg", "reorder_level_kg", "warehouse_id"]}]},
                {"aim": "cold storage effect on quality", "description": "Analyze if cold-stored inventory correlates with better quality grades", "benefits": "Optimize storage conditions to reduce defect rates", "datasets": ["japan_fruit_inventory", "japan_supplier_quality"], "columns": [{"dataset": "japan_fruit_inventory", "names": ["cold_storage", "fruit_name", "prefecture", "supplier_id"]}, {"dataset": "japan_supplier_quality", "names": ["supplier_id", "quality_score_2025", "quality_score_2026"]}]},
            ],
            "verified": True,
            "global_version": 1,
            "status": "active",
            "maintained_by": "mock_fill",
        }

        qual_dataset = {
            "line_name": LINE_NAME,
            "dataset_name": TERTIARY,
            "synonyms": synonyms,
            "description": "Supplier quality scores, certifications, and contract terms for Japanese fruit farms",
            "source_type": "pg",
            "source_config": {"url": pg_url, "schema": "public", "table": TERTIARY},
            "column_definitions": QUALITY_COLUMNS,
            "role": "tertiary",
            "join_hints": [
                {
                    "to_dataset": SECONDARY,
                    "on": ["supplier_id"],
                    "note": "Link supplier quality to inventory supplier records",
                },
                {
                    "to_dataset": PRIMARY,
                    "on": ["prefecture", "fruit_name"],
                    "note": "Link supplier quality to sales by prefecture and fruit",
                },
            ],
            "suggested_aims": [
                {"aim": "quality score trends by prefecture", "description": "Supplier quality grades over time by region", "benefits": "Identify declining suppliers early for corrective action", "columns": [{"dataset": "japan_supplier_quality", "names": ["prefecture", "quality_score_2025", "quality_score_2026"]}]},
                {"aim": "on-time delivery by fruit type", "description": "Delivery reliability analysis per fruit variety", "benefits": "Negotiate better terms with reliable suppliers", "columns": [{"dataset": "japan_supplier_quality", "names": ["fruit_name", "delivery_on_time_pct", "supplier_name"]}]},
                {"aim": "end-to-end fruit profitability", "description": "Full chain analysis from supplier quality through inventory cost to sales revenue", "benefits": "Complete profitability picture per fruit across the supply chain", "datasets": ["japan_fruit_sales", "japan_fruit_inventory", "japan_supplier_quality"], "columns": [{"dataset": "japan_fruit_sales", "names": ["prefecture", "fruit_name", "total_yen", "quantity_kg"]}, {"dataset": "japan_fruit_inventory", "names": ["prefecture", "fruit_name", "stock_quantity_kg", "storage_cost_yen_per_kg"]}, {"dataset": "japan_supplier_quality", "names": ["supplier_id", "prefecture", "fruit_name", "quality_score_2025", "contract_price_yen_per_kg"]}]},
            ],
            "verified": True,
            "global_version": 1,
            "status": "active",
            "maintained_by": "mock_fill",
        }

        await _upsert_registry(db, sales_dataset, now)
        await _upsert_registry(db, inv_dataset, now)
        await _upsert_registry(db, qual_dataset, now)
        await db.commit()

        date_cols = {
            PRIMARY: "sale_date",
            SECONDARY: "inventory_date",
        }
        for table_name, col in date_cols.items():
            result = await db.execute(
                text(f"SELECT MIN({col}) FROM {table_name}")
            )
            min_date = result.scalar_one_or_none()
            if min_date:
                await db.execute(
                    text("UPDATE global_registry SET data_earliest_ts = :ts WHERE dataset_name = :ds"),
                    {"ts": min_date, "ds": table_name},
                )
        await db.commit()

    print(f"Seeded {LINE_NAME}: {sales_count} sales, {inv_count} inventory, {qual_count} quality rows")
    print(f"Datasets registered: {PRIMARY}, {SECONDARY}, {TERTIARY}")
    print("Cross-join ready via prefecture, fruit_name, and supplier_id")


def main() -> None:
    asyncio.run(fill())


if __name__ == "__main__":
    main()
