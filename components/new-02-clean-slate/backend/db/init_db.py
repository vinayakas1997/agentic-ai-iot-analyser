"""Create all tables and seed test data. Idempotent — safe to run multiple times."""

import asyncio
import csv
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from config import get_settings
from db.models import Base, GlobalRegistry
from db.session import engine, AsyncSessionLocal

DATA_DIR = Path(__file__).resolve().parent / "mock_data"


async def create_tables() -> None:
    async with engine.begin() as conn:
        # Core tables
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS global_registry (
                id                  SERIAL PRIMARY KEY,
                line_name           TEXT NOT NULL,
                dataset_name        TEXT NOT NULL,
                synonyms            JSONB,
                description         TEXT,
                source_type         TEXT NOT NULL,
                source_config       JSONB NOT NULL,
                column_definitions  JSONB NOT NULL,
                role                TEXT,
                join_hints          JSONB,
                suggested_aims      JSONB,
                data_earliest_ts    TIMESTAMPTZ,
                verified            BOOLEAN DEFAULT TRUE,
                global_version      INT NOT NULL DEFAULT 1,
                status              TEXT DEFAULT 'active',
                maintained_by       TEXT,
                created_at          TIMESTAMPTZ DEFAULT NOW(),
                updated_at          TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (line_name, dataset_name)
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_global_registry_line_name ON global_registry(line_name)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_global_registry_status ON global_registry(status)"))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS task_registry (
                id              SERIAL PRIMARY KEY,
                user_id         TEXT NOT NULL,
                line_name       TEXT NOT NULL,
                version         INT NOT NULL DEFAULT 1,
                task_definition JSONB NOT NULL,
                UNIQUE (user_id, line_name, version)
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_task_registry_user_id ON task_registry(user_id)"))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS manager_sessions (
                session_id  TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                phase       TEXT NOT NULL DEFAULT 'lines',
                status      TEXT NOT NULL DEFAULT 'active',
                line_name   TEXT,
                title       TEXT,
                mode        VARCHAR(10) NOT NULL DEFAULT 'ask',
                state_json  JSONB NOT NULL DEFAULT '{}',
                version     INT NOT NULL DEFAULT 1,
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_manager_sessions_user ON manager_sessions(user_id, updated_at DESC)"))

        # Mock data tables
        await conn.execute(text("DROP TABLE IF EXISTS test_fruits CASCADE"))
        await conn.execute(text("""
            CREATE TABLE test_fruits (
                sale_date       DATE, sale_time TIME, fruits_id INT, fruits_name TEXT,
                cost            NUMERIC(10,2), quantity INT, store_id TEXT, category TEXT,
                supplier        TEXT, unit TEXT, discount_pct NUMERIC(5,2), tax NUMERIC(10,2),
                total           NUMERIC(10,2), region TEXT, country TEXT, organic BOOLEAN,
                batch_id        TEXT, shelf_life_days INT, warehouse TEXT, notes TEXT
            )
        """))
        await conn.execute(text("DROP TABLE IF EXISTS test_fruit_quality CASCADE"))
        await conn.execute(text("""
            CREATE TABLE test_fruit_quality (
                batch_id TEXT NOT NULL, inspection_date DATE, defect_rate NUMERIC(5,2),
                quality_grade TEXT, inspector_id TEXT, temperature_c NUMERIC(4,1),
                humidity_pct NUMERIC(5,2), notes TEXT
            )
        """))
        await conn.execute(text("DROP TABLE IF EXISTS japan_fruit_sales CASCADE"))
        await conn.execute(text("""
            CREATE TABLE japan_fruit_sales (
                sale_id SERIAL PRIMARY KEY, sale_date DATE NOT NULL, prefecture TEXT NOT NULL,
                city TEXT, fruit_name TEXT NOT NULL, variety TEXT, quantity_kg NUMERIC(8,2),
                price_per_kg_yen NUMERIC(8,2), total_yen NUMERIC(10,2), store_type TEXT,
                season TEXT, festival_season BOOLEAN DEFAULT FALSE
            )
        """))
        await conn.execute(text("DROP TABLE IF EXISTS japan_fruit_inventory CASCADE"))
        await conn.execute(text("""
            CREATE TABLE japan_fruit_inventory (
                inventory_id SERIAL PRIMARY KEY, inventory_date DATE NOT NULL,
                prefecture TEXT NOT NULL, fruit_name TEXT NOT NULL, variety TEXT,
                warehouse_id TEXT, warehouse_city TEXT, stock_quantity_kg NUMERIC(8,2),
                reorder_level_kg NUMERIC(8,2), supplier_id TEXT, supplier_name TEXT,
                lead_time_days INT, storage_cost_yen_per_kg NUMERIC(6,2),
                cold_storage BOOLEAN DEFAULT FALSE
            )
        """))
        await conn.execute(text("DROP TABLE IF EXISTS japan_supplier_quality CASCADE"))
        await conn.execute(text("""
            CREATE TABLE japan_supplier_quality (
                supplier_id TEXT NOT NULL PRIMARY KEY, supplier_name TEXT NOT NULL,
                prefecture TEXT, fruit_name TEXT, certification_type TEXT,
                quality_score_2025 NUMERIC(4,1), quality_score_2026 NUMERIC(4,1),
                delivery_on_time_pct NUMERIC(5,1), contract_price_yen_per_kg NUMERIC(8,2),
                farm_size_hectares NUMERIC(6,1), organic_certified BOOLEAN DEFAULT FALSE,
                established_year INT, notes TEXT
            )
        """))

    print("All tables created")


def _pg_url() -> str:
    return get_settings().db_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _load_csv(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


async def seed_fruits() -> None:
    now = datetime.now(timezone.utc)
    pg_url = _pg_url()
    synonyms = ["Vinayaka", "Vinayaka fruits", "FRUITS_TEST", "fruits test"]

    fruits_cols = [
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
    quality_cols = [
        {"name": "batch_id", "datatype": "text", "meaning": "batch identifier"},
        {"name": "inspection_date", "datatype": "date", "meaning": "inspection date"},
        {"name": "defect_rate", "datatype": "numeric", "meaning": "defect rate percentage"},
        {"name": "quality_grade", "datatype": "text", "meaning": "quality grade A/B/C"},
        {"name": "inspector_id", "datatype": "text", "meaning": "inspector identifier"},
        {"name": "temperature_c", "datatype": "numeric", "meaning": "storage temperature Celsius"},
        {"name": "humidity_pct", "datatype": "numeric", "meaning": "storage humidity percent"},
        {"name": "notes", "datatype": "text", "meaning": "inspection notes"},
    ]

    # Seed test_fruits data
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

    async with AsyncSessionLocal() as db:
        await db.execute(text("TRUNCATE TABLE test_fruits RESTART IDENTITY CASCADE"))
        await db.execute(text("TRUNCATE TABLE test_fruit_quality RESTART IDENTITY CASCADE"))
        # Insert test_fruits rows
        for row in fruits_rows:
            await db.execute(text("""
                INSERT INTO test_fruits (sale_date, sale_time, fruits_id, fruits_name, cost, quantity,
                    store_id, category, supplier, unit, discount_pct, tax, total, region, country,
                    organic, batch_id, shelf_life_days, warehouse, notes)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13, :14, :15, :16, :17, :18, :19, :20)
            """), {
                "1": date.fromisoformat(row[0]) if isinstance(row[0], str) else row[0],
                "2": time.fromisoformat(row[1]) if isinstance(row[1], str) else row[1],
                "3": row[2], "4": row[3], "5": row[4],
                "6": row[5], "7": row[6], "8": row[7], "9": row[8], "10": row[9],
                "11": row[10], "12": row[11], "13": row[12], "14": row[13], "15": row[14],
                "16": row[15], "17": row[16], "18": row[17], "19": row[18], "20": row[19],
            })
        for row in quality_rows:
            await db.execute(text("""
                INSERT INTO test_fruit_quality (batch_id, inspection_date, defect_rate, quality_grade, inspector_id, temperature_c, humidity_pct, notes)
                VALUES (:1, :2, :3, :4, :5, :6, :7, :8)
            """), {"1": row[0], "2": date.fromisoformat(row[1]) if isinstance(row[1], str) else row[1], "3": row[2], "4": row[3], "5": row[4], "6": row[5], "7": row[6], "8": row[7]})
        await db.commit()

    # Register in global_registry
    async with AsyncSessionLocal() as db:
        stmt = insert(GlobalRegistry).values(
            line_name="FRUITS_TEST", dataset_name="fruits", synonyms=synonyms,
            description="Test fruits sales dataset", source_type="pg",
            source_config={"url": pg_url, "schema": "public", "table": "test_fruits"},
            column_definitions=fruits_cols, role="primary",
            suggested_aims=[
                {"aim": "average cost by fruit", "description": "Compute average cost per fruit", "benefits": "Understand pricing structure"},
                {"aim": "sales by region", "description": "Total sales grouped by region", "benefits": "Regional performance analysis"},
            ],
            verified=True, global_version=1, status="active", maintained_by="iot_test",
        )
        await db.execute(stmt.on_conflict_do_update(
            index_elements=["line_name", "dataset_name"],
            set_={"description": "Test fruits sales dataset", "role": "primary", "suggested_aims": [
                {"aim": "average cost by fruit", "description": "Compute average cost per fruit", "benefits": "Understand pricing structure"},
                {"aim": "sales by region", "description": "Total sales grouped by region", "benefits": "Regional performance analysis"},
            ]}
        ))
        stmt2 = insert(GlobalRegistry).values(
            line_name="FRUITS_TEST", dataset_name="fruit_quality", synonyms=synonyms,
            description="Fruit batch quality inspections", source_type="pg",
            source_config={"url": pg_url, "schema": "public", "table": "test_fruit_quality"},
            column_definitions=quality_cols, role="secondary",
            join_hints={"to_dataset": "fruits", "on": ["batch_id"], "note": "Link quality inspections to sales batches"},
            suggested_aims=[
                {"aim": "defect rate by quality grade", "description": "Average defect rate per grade", "benefits": "Quality control insights"},
                {"aim": "average defect rate by batch", "description": "Defect rate trends across batches", "benefits": "Batch-level quality tracking"},
            ],
            verified=True, global_version=1, status="active", maintained_by="iot_test",
        )
        await db.execute(stmt2.on_conflict_do_update(
            index_elements=["line_name", "dataset_name"],
            set_={"description": "Fruit batch quality inspections", "role": "secondary", "suggested_aims": [
                {"aim": "defect rate by quality grade", "description": "Average defect rate per grade", "benefits": "Quality control insights"},
                {"aim": "average defect rate by batch", "description": "Defect rate trends across batches", "benefits": "Batch-level quality tracking"},
            ]}
        ))
        await db.commit()

    print(f"Seeded FRUITS_TEST: fruits=10 rows, fruit_quality=10 rows")


async def seed_japan() -> None:
    now = datetime.now(timezone.utc)
    pg_url = _pg_url()
    synonyms = ["Japan scenarios", "JAPAN_SCENARIOS", "Japanese fruit data", "japan", "japan fruit", "JP_FRUIT"]
    LINE = "JAPAN_SCENARIOS"

    sales_cols = [
        {"name": "sale_id", "datatype": "int"}, {"name": "sale_date", "datatype": "date"},
        {"name": "prefecture", "datatype": "text"}, {"name": "city", "datatype": "text"},
        {"name": "fruit_name", "datatype": "text"}, {"name": "variety", "datatype": "text"},
        {"name": "quantity_kg", "datatype": "numeric"}, {"name": "price_per_kg_yen", "datatype": "numeric"},
        {"name": "total_yen", "datatype": "numeric"}, {"name": "store_type", "datatype": "text"},
        {"name": "season", "datatype": "text"}, {"name": "festival_season", "datatype": "boolean"},
    ]
    inv_cols = [
        {"name": "inventory_id", "datatype": "int"}, {"name": "inventory_date", "datatype": "date"},
        {"name": "prefecture", "datatype": "text"}, {"name": "fruit_name", "datatype": "text"},
        {"name": "variety", "datatype": "text"}, {"name": "warehouse_id", "datatype": "text"},
        {"name": "warehouse_city", "datatype": "text"}, {"name": "stock_quantity_kg", "datatype": "numeric"},
        {"name": "reorder_level_kg", "datatype": "numeric"}, {"name": "supplier_id", "datatype": "text"},
        {"name": "supplier_name", "datatype": "text"}, {"name": "lead_time_days", "datatype": "int"},
        {"name": "storage_cost_yen_per_kg", "datatype": "numeric"}, {"name": "cold_storage", "datatype": "boolean"},
    ]
    qual_cols = [
        {"name": "supplier_id", "datatype": "text"}, {"name": "supplier_name", "datatype": "text"},
        {"name": "prefecture", "datatype": "text"}, {"name": "fruit_name", "datatype": "text"},
        {"name": "certification_type", "datatype": "text"}, {"name": "quality_score_2025", "datatype": "numeric"},
        {"name": "quality_score_2026", "datatype": "numeric"}, {"name": "delivery_on_time_pct", "datatype": "numeric"},
        {"name": "contract_price_yen_per_kg", "datatype": "numeric"}, {"name": "farm_size_hectares", "datatype": "numeric"},
        {"name": "organic_certified", "datatype": "boolean"}, {"name": "established_year", "datatype": "int"},
        {"name": "notes", "datatype": "text"},
    ]

    # Insert CSV data
    for table, filename, col_defs in [
        ("japan_fruit_sales", "scenario_1_japan_fruit_sales.csv", sales_cols),
        ("japan_fruit_inventory", "scenario_2_fruit_inventory_japan.csv", inv_cols),
        ("japan_supplier_quality", "scenario_3_supplier_quality_japan.csv", qual_cols),
    ]:
        rows = _load_csv(filename)
        async with AsyncSessionLocal() as db:
            await db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            for row in rows:
                converted = _convert_row(row, col_defs)
                cols = ", ".join(converted.keys())
                vals = ", ".join([f":{k}" for k in converted.keys()])
                await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({vals})"), converted)
            await db.commit()
        print(f"  {table}: {len(rows)} rows")

    # Register in global_registry (simplified — keep JAPAN_SCENARIOS aimed for workspace)
    suggested_sales = [
        {"aim": "total sales by prefecture", "description": "Revenue across Japanese prefectures", "benefits": "Identify top regions", "columns": [{"dataset": "japan_fruit_sales", "names": ["prefecture", "total_yen"]}]},
        {"aim": "average price per kg by fruit and season", "description": "Seasonal price trends", "benefits": "Optimize pricing", "columns": [{"dataset": "japan_fruit_sales", "names": ["fruit_name", "season", "price_per_kg_yen"]}]},
    ]
    suggested_inv = [
        {"aim": "stock levels by prefecture and fruit", "description": "Current inventory distribution", "benefits": "Balance stock", "columns": [{"dataset": "japan_fruit_inventory", "names": ["prefecture", "fruit_name", "stock_quantity_kg"]}]},
        {"aim": "reorder risk by fruit", "description": "Items near reorder threshold", "benefits": "Proactive restocking", "columns": [{"dataset": "japan_fruit_inventory", "names": ["fruit_name", "stock_quantity_kg", "reorder_level_kg"]}]},
    ]
    suggested_qual = [
        {"aim": "quality score trends by prefecture", "description": "Supplier quality over time", "benefits": "Identify declining suppliers", "columns": [{"dataset": "japan_supplier_quality", "names": ["prefecture", "quality_score_2025", "quality_score_2026"]}]},
        {"aim": "on-time delivery by fruit type", "description": "Delivery reliability analysis", "benefits": "Negotiate better terms", "columns": [{"dataset": "japan_supplier_quality", "names": ["fruit_name", "delivery_on_time_pct", "supplier_name"]}]},
    ]

    async with AsyncSessionLocal() as db:
        for ds_name, aims in [("japan_fruit_sales", suggested_sales), ("japan_fruit_inventory", suggested_inv), ("japan_supplier_quality", suggested_qual)]:
            stmt = insert(GlobalRegistry).values(
                line_name=LINE, dataset_name=ds_name, synonyms=synonyms,
                description=f"{ds_name} dataset", source_type="pg",
                source_config={"url": pg_url, "schema": "public", "table": ds_name},
                column_definitions=sales_cols if ds_name == "japan_fruit_sales" else inv_cols if ds_name == "japan_fruit_inventory" else qual_cols,
                role="primary" if ds_name == "japan_fruit_sales" else "secondary" if ds_name == "japan_fruit_inventory" else "tertiary",
                suggested_aims=aims, verified=True, global_version=1, status="active", maintained_by="mock_fill",
            )
            await db.execute(stmt.on_conflict_do_update(
                index_elements=["line_name", "dataset_name"],
                set_={"description": f"{ds_name} dataset", "suggested_aims": aims}
            ))
        await db.commit()

    print(f"Seeded JAPAN_SCENARIOS: 3 datasets registered")


async def init_db() -> None:
    print("=== Creating tables ===")
    await create_tables()
    print("=== Seeding FRUITS_TEST ===")
    await seed_fruits()
    print("=== Seeding JAPAN_SCENARIOS ===")
    await seed_japan()
    print("=== init_db complete ===")


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
