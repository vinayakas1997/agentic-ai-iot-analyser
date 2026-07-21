-- Quality inspection data linked to test_fruits via batch_id

DROP TABLE IF EXISTS test_fruit_quality CASCADE;

CREATE TABLE test_fruit_quality (
    batch_id          TEXT NOT NULL,
    inspection_date   DATE,
    defect_rate       NUMERIC(5, 2),
    quality_grade     TEXT,
    inspector_id      TEXT,
    temperature_c     NUMERIC(4, 1),
    humidity_pct      NUMERIC(5, 2),
    notes             TEXT
);

INSERT INTO test_fruit_quality VALUES
('BATCH-A01', '2026-06-01', 1.20, 'A', 'INS-01', 4.5, 62.0, 'Good condition'),
('BATCH-B01', '2026-06-01', 2.80, 'B', 'INS-02', 5.0, 58.0, NULL),
('BATCH-M01', '2026-06-01', 0.90, 'A', 'INS-01', 6.2, 65.0, 'Premium'),
('BATCH-O01', '2026-06-01', 3.10, 'B', 'INS-03', 4.8, 60.0, 'Minor bruising'),
('BATCH-G01', '2026-06-02', 1.50, 'A', 'INS-02', 3.9, 55.0, NULL),
('BATCH-P01', '2026-06-02', 4.20, 'C', 'INS-03', 7.1, 70.0, 'Ripeness concern'),
('BATCH-S01', '2026-06-02', 0.70, 'A', 'INS-01', 2.5, 50.0, 'Organic certified'),
('BATCH-W01', '2026-06-02', 2.00, 'B', 'INS-02', 5.5, 63.0, NULL),
('BATCH-K01', '2026-06-03', 1.80, 'A', 'INS-01', 4.0, 57.0, NULL),
('BATCH-PC01', '2026-06-03', 2.40, 'B', 'INS-03', 5.2, 61.0, 'Soft spots');
