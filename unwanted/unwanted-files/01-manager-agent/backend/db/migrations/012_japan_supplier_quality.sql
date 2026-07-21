DROP TABLE IF EXISTS japan_supplier_quality CASCADE;

CREATE TABLE japan_supplier_quality (
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
