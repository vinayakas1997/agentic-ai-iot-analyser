DROP TABLE IF EXISTS japan_fruit_sales CASCADE;

CREATE TABLE japan_fruit_sales (
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
