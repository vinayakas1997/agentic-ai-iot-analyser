"""Standalone script to fill mock data into the PostgreSQL database.

Usage:
    python mock-database-fill/fill_mock_data.py

Reads DB_URL from environment, or defaults to local Docker instance.
"""

import asyncio
import csv
import json
import os
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATA_DIR = Path(__file__).resolve().parent
FALLBACK_DB_URL = os.environ.get(
    "DB_URL",
    "postgresql+asyncpg://manager_agent:manager_agent_pass@localhost:5432/manager_agent_db",
)

# ── FRUITS_TEST ──

FRUITS_LINE = "FRUITS_TEST"
FRUITS_SYNONYMS = ["Vinayaka", "Vinayaka fruits", "FRUITS_TEST", "fruits test"]

FRUITS_COLUMNS = [
    {"name": "sale_date", "datatype": "date", "meaning": "date of sale"},
    {"name": "sale_time", "datatype": "time", "meaning": "time of sale"},
    {"name": "fruits_id", "datatype": "int", "meaning": "fruit product id"},
    {"name": "fruits_name", "datatype": "text", "meaning": "fruit name"},
    {"name": "cost", "datatype": "numeric", "meaning": "unit cost"},
    {"name": "quantity", "datatype": "int", "meaning": "quantity sold"},
    {"name": "store_id", "datatype": "text", "meaning": "store identifier"},
    {"name": "category", "datatype": "text", "meaning": "fruit category"},
    {"name": "supplier", "datatype": "text", "meaning": "supplier name"},
    {"name": "unit", "datatype": "text", "meaning": "unit of measure"},
    {"name": "discount_pct", "datatype": "numeric", "meaning": "discount percentage"},
    {"name": "tax", "datatype": "numeric", "meaning": "tax amount"},
    {"name": "total", "datatype": "numeric", "meaning": "total sale amount"},
    {"name": "region", "datatype": "text", "meaning": "sales region"},
    {"name": "country", "datatype": "text", "meaning": "country"},
    {"name": "organic", "datatype": "boolean", "meaning": "organic flag"},
    {"name": "batch_id", "datatype": "text", "meaning": "batch identifier"},
    {"name": "shelf_life_days", "datatype": "int", "meaning": "shelf life in days"},
    {"name": "warehouse", "datatype": "text", "meaning": "warehouse code"},
    {"name": "notes", "datatype": "text", "meaning": "optional notes"},
]

QUALITY_COLUMNS = [
    {"name": "batch_id", "datatype": "text", "meaning": "batch identifier"},
    {"name": "inspection_date", "datatype": "date", "meaning": "inspection date"},
    {"name": "defect_rate", "datatype": "numeric", "meaning": "defect rate percentage"},
    {"name": "quality_grade", "datatype": "text", "meaning": "quality grade A/B/C"},
    {"name": "inspector_id", "datatype": "text", "meaning": "inspector identifier"},
    {"name": "temperature_c", "datatype": "numeric", "meaning": "storage temperature Celsius"},
    {"name": "humidity_pct", "datatype": "numeric", "meaning": "storage humidity percent"},
    {"name": "notes", "datatype": "text", "meaning": "inspection notes"},
]

# ── JAPAN_SCENARIOS ──

JAPAN_LINE = "JAPAN_SCENARIOS"
JAPAN_SYNONYMS = [
    "Japan scenarios", "JAPAN_SCENARIOS", "Japanese fruit data",
    "japan", "japan fruit", "JP_FRUIT",
]

SALES_COLUMNS = [
    {"name": "sale_id", "meaning": "unique sale identifier", "datatype": "serial"},
    {"name": "sale_date", "meaning": "date of sale", "datatype": "date"},
    {"name": "prefecture", "meaning": "Japanese prefecture", "datatype": "text"},
    {"name": "city", "meaning": "city within prefecture", "datatype": "text"},
    {"name": "fruit_name", "meaning": "fruit name in English", "datatype": "text"},
    {"name": "variety", "meaning": "Japanese fruit variety", "datatype": "text"},
    {"name": "quantity_kg", "meaning": "quantity sold in kilograms", "datatype": "numeric"},
    {"name": "price_per_kg_yen", "meaning": "price per kilogram in JPY", "datatype": "numeric"},
    {"name": "total_yen", "meaning": "total sale amount in JPY", "datatype": "numeric"},
    {"name": "store_type", "meaning": "type of retail store", "datatype": "text"},
    {"name": "season", "meaning": "season of sale", "datatype": "text"},
    {"name": "festival_season", "meaning": "whether sold during a festival period", "datatype": "boolean"},
]

INVENTORY_COLUMNS = [
    {"name": "inventory_id", "meaning": "unique inventory identifier", "datatype": "serial"},
    {"name": "inventory_date", "meaning": "date of inventory record", "datatype": "date"},
    {"name": "prefecture", "meaning": "Japanese prefecture", "datatype": "text"},
    {"name": "fruit_name", "meaning": "fruit name in English", "datatype": "text"},
    {"name": "variety", "meaning": "Japanese fruit variety", "datatype": "text"},
    {"name": "warehouse_id", "meaning": "warehouse code", "datatype": "text"},
    {"name": "warehouse_city", "meaning": "city where warehouse is located", "datatype": "text"},
    {"name": "stock_quantity_kg", "meaning": "current stock in kg", "datatype": "numeric"},
    {"name": "reorder_level_kg", "meaning": "minimum stock before reorder", "datatype": "numeric"},
    {"name": "supplier_id", "meaning": "supplier identifier", "datatype": "text"},
    {"name": "supplier_name", "meaning": "supplier company name", "datatype": "text"},
    {"name": "lead_time_days", "meaning": "days from order to delivery", "datatype": "int"},
    {"name": "storage_cost_yen_per_kg", "meaning": "daily storage cost per kg in JPY", "datatype": "numeric"},
    {"name": "cold_storage", "meaning": "whether requires refrigeration", "datatype": "boolean"},
]

SUPPLIER_COLUMNS = [
    {"name": "supplier_id", "meaning": "unique supplier code", "datatype": "text"},
    {"name": "supplier_name", "meaning": "supplier company name", "datatype": "text"},
    {"name": "prefecture", "meaning": "prefecture of supplier farm", "datatype": "text"},
    {"name": "fruit_name", "meaning": "primary fruit supplied", "datatype": "text"},
    {"name": "certification_type", "meaning": "quality certification held", "datatype": "text"},
    {"name": "quality_score_2025", "meaning": "quality score out of 100 for 2025", "datatype": "numeric"},
    {"name": "quality_score_2026", "meaning": "quality score out of 100 for 2026", "datatype": "numeric"},
    {"name": "delivery_on_time_pct", "meaning": "on-time delivery percentage", "datatype": "numeric"},
    {"name": "contract_price_yen_per_kg", "meaning": "contract price per kg in JPY", "datatype": "numeric"},
    {"name": "farm_size_hectares", "meaning": "size of farm in hectares", "datatype": "numeric"},
    {"name": "organic_certified", "meaning": "whether JAS organic certified", "datatype": "boolean"},
    {"name": "established_year", "meaning": "year the farm was established", "datatype": "int"},
    {"name": "notes", "meaning": "additional notes", "datatype": "text"},
]

# ── DDL ──

CREATE_FRUITS = """
    CREATE TABLE IF NOT EXISTS test_fruits (
        sale_date DATE, sale_time TIME, fruits_id INT, fruits_name TEXT,
        cost NUMERIC(10,2), quantity INT, store_id TEXT, category TEXT,
        supplier TEXT, unit TEXT, discount_pct NUMERIC(5,2), tax NUMERIC(10,2),
        total NUMERIC(10,2), region TEXT, country TEXT, organic BOOLEAN,
        batch_id TEXT, shelf_life_days INT, warehouse TEXT, notes TEXT
    )
"""

CREATE_QUALITY = """
    CREATE TABLE IF NOT EXISTS test_fruit_quality (
        batch_id TEXT NOT NULL, inspection_date DATE, defect_rate NUMERIC(5,2),
        quality_grade TEXT, inspector_id TEXT, temperature_c NUMERIC(4,1),
        humidity_pct NUMERIC(5,2), notes TEXT
    )
"""

CREATE_SALES = """
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
    )
"""

CREATE_INVENTORY = """
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
    )
"""

CREATE_SUPPLIER_QUALITY = """
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
    )
"""


def _load_csv(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


async def _ensure_tables(db: AsyncSession) -> None:
    for ddl in [CREATE_FRUITS, CREATE_QUALITY, CREATE_SALES, CREATE_INVENTORY, CREATE_SUPPLIER_QUALITY]:
        await db.execute(text(ddl))


async def _upsert_registry(db: AsyncSession, values: dict, now: datetime) -> None:
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
        "synonyms": json.dumps(values.get("synonyms", [])),
        "description": values.get("description"),
        "source_type": values["source_type"],
        "source_config": json.dumps(values["source_config"]),
        "column_definitions": json.dumps(values["column_definitions"]),
        "role": values.get("role"),
        "join_hints": json.dumps(values.get("join_hints")),
        "suggested_aims": json.dumps(values.get("suggested_aims", [])),
        "verified": values["verified"],
        "global_version": values["global_version"],
        "status": values["status"],
        "maintained_by": values.get("maintained_by"),
        "updated_at": now,
    })


def _coerce_sales(row: dict) -> dict:
    r = dict(row)
    if isinstance(r.get("sale_date"), str):
        r["sale_date"] = date.fromisoformat(r["sale_date"])
    if isinstance(r.get("festival_season"), str):
        r["festival_season"] = r["festival_season"].lower() == "true"
    for c in ["quantity_kg", "price_per_kg_yen", "total_yen"]:
        if isinstance(r.get(c), str):
            r[c] = Decimal(r[c])
    return r


def _coerce_inventory(row: dict) -> dict:
    r = dict(row)
    if isinstance(r.get("inventory_date"), str):
        r["inventory_date"] = date.fromisoformat(r["inventory_date"])
    if isinstance(r.get("cold_storage"), str):
        r["cold_storage"] = r["cold_storage"].lower() == "true"
    if isinstance(r.get("lead_time_days"), str):
        r["lead_time_days"] = int(r["lead_time_days"])
    for c in ["stock_quantity_kg", "reorder_level_kg", "storage_cost_yen_per_kg"]:
        if isinstance(r.get(c), str):
            r[c] = Decimal(r[c])
    return r


def _coerce_quality(row: dict) -> dict:
    r = dict(row)
    if isinstance(r.get("organic_certified"), str):
        r["organic_certified"] = r["organic_certified"].lower() == "true"
    if isinstance(r.get("established_year"), str):
        r["established_year"] = int(r["established_year"])
    for c in ["quality_score_2025", "quality_score_2026", "delivery_on_time_pct",
              "contract_price_yen_per_kg", "farm_size_hectares"]:
        if isinstance(r.get(c), str):
            r[c] = Decimal(r[c])
    return r


async def _truncate_and_insert(db: AsyncSession, table: str, rows: list[dict],
                                coerce: Callable[[dict], dict] | None = None) -> int:
    await db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    col_names = ", ".join(cols)
    stmt = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})")
    for row in rows:
        await db.execute(stmt, coerce(row) if coerce else row)
    return len(rows)


async def seed_fruits(db: AsyncSession, pg_url: str, now: datetime) -> None:
    fruits_rows = [
        ('2026-06-01', '09:15:00', 1, 'Apple', 1.25, 12, 'ST001', 'Pome', 'FreshFarm Co', 'kg', 0.00, 1.80, 16.80, 'West', 'USA', True, 'BATCH-A01', 21, 'WH-W1', 'Morning delivery'),
        ('2026-06-01', '10:30:00', 2, 'Banana', 0.45, 24, 'ST001', 'Tropical', 'TropicSupply', 'kg', 5.00, 0.86, 11.26, 'West', 'USA', False, 'BATCH-B01', 7, 'WH-W1', None),
        ('2026-06-01', '11:00:00', 3, 'Mango', 2.50, 8, 'ST002', 'Tropical', 'TropicSupply', 'kg', 0.00, 2.00, 22.00, 'South', 'USA', True, 'BATCH-M01', 10, 'WH-S1', 'Premium grade'),
        ('2026-06-01', '12:45:00', 4, 'Orange', 1.80, 15, 'ST002', 'Citrus', 'CitrusHub', 'kg', 10.00, 2.03, 26.33, 'South', 'USA', False, 'BATCH-O01', 14, 'WH-S1', 'Promo week'),
        ('2026-06-01', '14:20:00', 5, 'Grapes', 3.20, 6, 'ST003', 'Berry', 'Vineyard Ltd', 'kg', 0.00, 1.54, 20.74, 'East', 'USA', True, 'BATCH-G01', 5, 'WH-E1', 'Seedless'),
        ('2026-06-02', '08:50:00', 6, 'Pineapple', 4.00, 4, 'ST003', 'Tropical', 'TropicSupply', 'each', 0.00, 1.28, 17.28, 'East', 'USA', False, 'BATCH-P01', 12, 'WH-E1', None),
        ('2026-06-02', '09:30:00', 7, 'Strawberry', 5.50, 3, 'ST004', 'Berry', 'BerryBest', 'box', 0.00, 0.99, 17.49, 'North', 'USA', True, 'BATCH-S01', 3, 'WH-N1', 'Organic box'),
        ('2026-06-02', '10:15:00', 8, 'Watermelon', 6.00, 2, 'ST004', 'Melon', 'FreshFarm Co', 'each', 15.00, 0.92, 11.12, 'North', 'USA', False, 'BATCH-W01', 7, 'WH-N1', 'Summer sale'),
        ('2026-06-02', '11:40:00', 9, 'Kiwi', 2.20, 10, 'ST005', 'Exotic', 'ExoticImport', 'kg', 0.00, 1.76, 23.76, 'West', 'USA', True, 'BATCH-K01', 18, 'WH-W2', None),
        ('2026-06-02', '13:00:00', 10, 'Peach', 2.80, 9, 'ST005', 'Stone', 'OrchardFresh', 'kg', 5.00, 1.99, 25.99, 'West', 'USA', False, 'BATCH-PC01', 8, 'WH-W2', 'Local orchard'),
    ]
    quality_rows = [
        ('BATCH-A01', '2026-06-01', 1.20, 'A', 'INS-01', 4.5, 62.0, 'Good condition'),
        ('BATCH-B01', '2026-06-01', 2.80, 'B', 'INS-02', 5.0, 58.0, None),
        ('BATCH-M01', '2026-06-01', 0.90, 'A', 'INS-01', 6.2, 65.0, 'Premium'),
        ('BATCH-O01', '2026-06-01', 3.10, 'B', 'INS-03', 4.8, 60.0, 'Minor bruising'),
        ('BATCH-G01', '2026-06-02', 1.50, 'A', 'INS-02', 3.9, 55.0, None),
        ('BATCH-P01', '2026-06-02', 4.20, 'C', 'INS-03', 7.1, 70.0, 'Ripeness concern'),
        ('BATCH-S01', '2026-06-02', 0.70, 'A', 'INS-01', 2.5, 50.0, 'Organic certified'),
        ('BATCH-W01', '2026-06-02', 2.00, 'B', 'INS-02', 5.5, 63.0, None),
        ('BATCH-K01', '2026-06-03', 1.80, 'A', 'INS-01', 4.0, 57.0, None),
        ('BATCH-PC01', '2026-06-03', 2.40, 'B', 'INS-03', 5.2, 61.0, 'Soft spots'),
    ]

    await db.execute(text("TRUNCATE TABLE test_fruits RESTART IDENTITY CASCADE"))
    await db.execute(text("TRUNCATE TABLE test_fruit_quality RESTART IDENTITY CASCADE"))

    cols_f = ["sale_date", "sale_time", "fruits_id", "fruits_name", "cost", "quantity", "store_id",
              "category", "supplier", "unit", "discount_pct", "tax", "total", "region", "country",
              "organic", "batch_id", "shelf_life_days", "warehouse", "notes"]
    ph_f = ", ".join([f":{c}" for c in cols_f])
    stmt_f = text(f"INSERT INTO test_fruits ({', '.join(cols_f)}) VALUES ({ph_f})")
    for row in fruits_rows:
        params = dict(zip(cols_f, row))
        if isinstance(params["sale_date"], str):
            params["sale_date"] = date.fromisoformat(params["sale_date"])
        if isinstance(params["sale_time"], str):
            parts = params["sale_time"].split(":")
            params["sale_time"] = time(int(parts[0]), int(parts[1]), int(parts[2]))
        if isinstance(params["organic"], str):
            params["organic"] = params["organic"].lower() == "true"
        await db.execute(stmt_f, params)

    cols_q = ["batch_id", "inspection_date", "defect_rate", "quality_grade", "inspector_id",
              "temperature_c", "humidity_pct", "notes"]
    ph_q = ", ".join([f":{c}" for c in cols_q])
    stmt_q = text(f"INSERT INTO test_fruit_quality ({', '.join(cols_q)}) VALUES ({ph_q})")
    for row in quality_rows:
        params = dict(zip(cols_q, row))
        if isinstance(params["inspection_date"], str):
            params["inspection_date"] = date.fromisoformat(params["inspection_date"])
        await db.execute(stmt_q, params)

    # Register in global_registry
    await _upsert_registry(db, {
        "line_name": FRUITS_LINE, "dataset_name": "fruits", "synonyms": FRUITS_SYNONYMS,
        "description": "Test fruits sales dataset", "source_type": "pg",
        "source_config": {"url": pg_url, "schema": "public", "table": "test_fruits"},
        "column_definitions": FRUITS_COLUMNS, "role": "primary",
        "suggested_aims": [
            {"aim": "average cost by fruit", "description": "Compute average cost per fruit", "benefits": "Understand pricing structure", "columns": [{"dataset": "fruits", "names": ["fruits_name", "cost", "quantity"]}]},
            {"aim": "sales by region", "description": "Total sales grouped by region", "benefits": "Regional performance analysis", "columns": [{"dataset": "fruits", "names": ["region", "total", "fruits_name"]}]},
        ],
        "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
    }, now)
    await _upsert_registry(db, {
        "line_name": FRUITS_LINE, "dataset_name": "fruit_quality", "synonyms": FRUITS_SYNONYMS,
        "description": "Fruit batch quality inspections", "source_type": "pg",
        "source_config": {"url": pg_url, "schema": "public", "table": "test_fruit_quality"},
        "column_definitions": QUALITY_COLUMNS, "role": "secondary",
        "join_hints": {"to_dataset": "fruits", "on": ["batch_id"], "note": "Link quality inspections to sales batches"},
        "suggested_aims": [
            {"aim": "defect rate by quality grade", "description": "Average defect rate per grade", "benefits": "Quality control insights", "columns": [{"dataset": "fruit_quality", "names": ["quality_grade", "defect_rate"]}]},
            {"aim": "average defect rate by batch", "description": "Defect rate trends across batches", "benefits": "Batch-level quality tracking", "columns": [{"dataset": "fruit_quality", "names": ["batch_id", "defect_rate"]}]},
        ],
        "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
    }, now)

    print(f"  FRUITS_TEST: 10 fruits + 10 quality rows registered")


async def seed_japan(db: AsyncSession, pg_url: str, now: datetime) -> None:
    sales_rows = _load_csv("scenario_1_japan_fruit_sales.csv")
    inv_rows = _load_csv("scenario_2_fruit_inventory_japan.csv")
    qual_rows = _load_csv("scenario_3_supplier_quality_japan.csv")

    sales_count = await _truncate_and_insert(db, "japan_fruit_sales", sales_rows, _coerce_sales)
    inv_count = await _truncate_and_insert(db, "japan_fruit_inventory", inv_rows, _coerce_inventory)
    qual_count = await _truncate_and_insert(db, "japan_supplier_quality", qual_rows, _coerce_quality)

    await _upsert_registry(db, {
        "line_name": JAPAN_LINE, "dataset_name": "japan_fruit_sales", "synonyms": JAPAN_SYNONYMS,
        "description": "Fruit sales across Japanese prefectures with varieties, prices, and seasonal trends",
        "source_type": "pg",
        "source_config": {"url": pg_url, "schema": "public", "table": "japan_fruit_sales"},
        "column_definitions": SALES_COLUMNS, "role": "primary",
        "suggested_aims": [
            {"aim": "total sales by prefecture", "description": "Revenue breakdown across Japanese prefectures", "benefits": "Identify top revenue regions", "columns": [{"dataset": "japan_fruit_sales", "names": ["prefecture", "total_yen"]}]},
            {"aim": "average price per kg by fruit and season", "description": "Seasonal price trends for each fruit variety", "benefits": "Optimize pricing strategy", "columns": [{"dataset": "japan_fruit_sales", "names": ["fruit_name", "season", "price_per_kg_yen"]}]},
            {"aim": "inventory turnover vs sales velocity", "description": "Compare inventory movement relative to sales", "benefits": "Identify slow-moving stock", "datasets": ["japan_fruit_sales", "japan_fruit_inventory"], "columns": [{"dataset": "japan_fruit_sales", "names": ["fruit_name", "quantity_kg"]}, {"dataset": "japan_fruit_inventory", "names": ["fruit_name", "stock_quantity_kg"]}]},
        ],
        "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
    }, now)
    await _upsert_registry(db, {
        "line_name": JAPAN_LINE, "dataset_name": "japan_fruit_inventory", "synonyms": JAPAN_SYNONYMS,
        "description": "Fruit warehouse inventory levels and supplier details across Japan",
        "source_type": "pg",
        "source_config": {"url": pg_url, "schema": "public", "table": "japan_fruit_inventory"},
        "column_definitions": INVENTORY_COLUMNS, "role": "secondary",
        "join_hints": {"to_dataset": "japan_fruit_sales", "on": ["prefecture", "fruit_name"], "note": "Link inventory to sales by prefecture and fruit"},
        "suggested_aims": [
            {"aim": "stock levels by prefecture and fruit", "description": "Current inventory distribution across warehouses", "benefits": "Prevent stockouts", "columns": [{"dataset": "japan_fruit_inventory", "names": ["prefecture", "fruit_name", "stock_quantity_kg"]}]},
            {"aim": "reorder risk by fruit", "description": "Items approaching reorder threshold", "benefits": "Proactive restocking", "columns": [{"dataset": "japan_fruit_inventory", "names": ["fruit_name", "stock_quantity_kg", "reorder_level_kg"]}]},
        ],
        "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
    }, now)
    await _upsert_registry(db, {
        "line_name": JAPAN_LINE, "dataset_name": "japan_supplier_quality", "synonyms": JAPAN_SYNONYMS,
        "description": "Supplier quality scores, certifications, and contract terms for Japanese fruit farms",
        "source_type": "pg",
        "source_config": {"url": pg_url, "schema": "public", "table": "japan_supplier_quality"},
        "column_definitions": SUPPLIER_COLUMNS, "role": "tertiary",
        "join_hints": [
            {"to_dataset": "japan_fruit_inventory", "on": ["supplier_id"], "note": "Link supplier quality to inventory"},
            {"to_dataset": "japan_fruit_sales", "on": ["prefecture", "fruit_name"], "note": "Link supplier quality to sales"},
        ],
        "suggested_aims": [
            {"aim": "quality score trends by prefecture", "description": "Supplier quality grades over time by region", "benefits": "Identify declining suppliers", "columns": [{"dataset": "japan_supplier_quality", "names": ["prefecture", "quality_score_2025", "quality_score_2026"]}]},
            {"aim": "on-time delivery by fruit type", "description": "Delivery reliability analysis per fruit variety", "benefits": "Negotiate better terms", "columns": [{"dataset": "japan_supplier_quality", "names": ["fruit_name", "delivery_on_time_pct", "supplier_name"]}]},
        ],
        "verified": True, "global_version": 1, "status": "active", "maintained_by": "mock_fill",
    }, now)

    print(f"  JAPAN_SCENARIOS: {sales_count} sales, {inv_count} inventory, {qual_count} quality rows")


async def fill(db_url: str | None = None) -> None:
    url = db_url or FALLBACK_DB_URL
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    pg_url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    async with SessionLocal() as db:
        await _ensure_tables(db)
        await seed_fruits(db, pg_url, now)
        await seed_japan(db, pg_url, now)
        await db.commit()

    print("Mock data fill complete!")
    await engine.dispose()


def main() -> None:
    asyncio.run(fill())


if __name__ == "__main__":
    main()
