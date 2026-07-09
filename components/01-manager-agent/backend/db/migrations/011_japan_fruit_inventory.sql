DROP TABLE IF EXISTS japan_fruit_inventory CASCADE;

CREATE TABLE japan_fruit_inventory (
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
