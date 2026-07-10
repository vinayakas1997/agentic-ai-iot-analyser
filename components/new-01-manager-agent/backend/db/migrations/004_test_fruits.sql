-- Test fruits source data (IoT sample table)
-- Same database as DB_URL. Registered in global_registry via seed_fruits_global.py

DROP TABLE IF EXISTS test_fruits CASCADE;

CREATE TABLE test_fruits (
    sale_date         DATE,
    sale_time         TIME,
    fruits_id         INT,
    fruits_name       TEXT,
    cost              NUMERIC(10, 2),
    quantity          INT,
    store_id          TEXT,
    category          TEXT,
    supplier          TEXT,
    unit              TEXT,
    discount_pct      NUMERIC(5, 2),
    tax               NUMERIC(10, 2),
    total             NUMERIC(10, 2),
    region            TEXT,
    country           TEXT,
    organic           BOOLEAN,
    batch_id          TEXT,
    shelf_life_days   INT,
    warehouse         TEXT,
    notes             TEXT
);

INSERT INTO test_fruits VALUES
('2026-06-01', '09:15:00', 1, 'Apple', 1.25, 12, 'ST001', 'Pome', 'FreshFarm Co', 'kg', 0.00, 1.80, 16.80, 'West', 'USA', true, 'BATCH-A01', 21, 'WH-W1', 'Morning delivery'),
('2026-06-01', '10:30:00', 2, 'Banana', 0.45, 24, 'ST001', 'Tropical', 'TropicSupply', 'kg', 5.00, 0.86, 11.26, 'West', 'USA', false, 'BATCH-B01', 7, 'WH-W1', NULL),
('2026-06-01', '11:00:00', 3, 'Mango', 2.50, 8, 'ST002', 'Tropical', 'TropicSupply', 'kg', 0.00, 2.00, 22.00, 'South', 'USA', true, 'BATCH-M01', 10, 'WH-S1', 'Premium grade'),
('2026-06-01', '12:45:00', 4, 'Orange', 1.80, 15, 'ST002', 'Citrus', 'CitrusHub', 'kg', 10.00, 2.03, 26.33, 'South', 'USA', false, 'BATCH-O01', 14, 'WH-S1', 'Promo week'),
('2026-06-01', '14:20:00', 5, 'Grapes', 3.20, 6, 'ST003', 'Berry', 'Vineyard Ltd', 'kg', 0.00, 1.54, 20.74, 'East', 'USA', true, 'BATCH-G01', 5, 'WH-E1', 'Seedless'),
('2026-06-02', '08:50:00', 6, 'Pineapple', 4.00, 4, 'ST003', 'Tropical', 'TropicSupply', 'each', 0.00, 1.28, 17.28, 'East', 'USA', false, 'BATCH-P01', 12, 'WH-E1', NULL),
('2026-06-02', '09:30:00', 7, 'Strawberry', 5.50, 3, 'ST004', 'Berry', 'BerryBest', 'box', 0.00, 0.99, 17.49, 'North', 'USA', true, 'BATCH-S01', 3, 'WH-N1', 'Organic box'),
('2026-06-02', '10:15:00', 8, 'Watermelon', 6.00, 2, 'ST004', 'Melon', 'FreshFarm Co', 'each', 15.00, 0.92, 11.12, 'North', 'USA', false, 'BATCH-W01', 7, 'WH-N1', 'Summer sale'),
('2026-06-02', '11:40:00', 9, 'Kiwi', 2.20, 10, 'ST005', 'Exotic', 'ExoticImport', 'kg', 0.00, 1.76, 23.76, 'West', 'USA', true, 'BATCH-K01', 18, 'WH-W2', NULL),
('2026-06-02', '13:00:00', 10, 'Peach', 2.80, 9, 'ST005', 'Stone', 'OrchardFresh', 'kg', 5.00, 1.99, 25.99, 'West', 'USA', false, 'BATCH-PC01', 8, 'WH-W2', 'Local orchard'),
('2026-06-03', '09:00:00', 11, 'Pear', 1.90, 11, 'ST001', 'Pome', 'OrchardFresh', 'kg', 0.00, 1.67, 22.57, 'West', 'USA', true, 'BATCH-PR01', 15, 'WH-W1', NULL),
('2026-06-03', '10:20:00', 12, 'Blueberry', 4.50, 5, 'ST002', 'Berry', 'BerryBest', 'box', 0.00, 1.13, 23.63, 'South', 'USA', true, 'BATCH-BB01', 4, 'WH-S1', 'Antioxidant promo'),
('2026-06-03', '11:55:00', 13, 'Papaya', 3.00, 7, 'ST003', 'Tropical', 'TropicSupply', 'each', 0.00, 1.47, 22.47, 'East', 'USA', false, 'BATCH-PA01', 6, 'WH-E1', NULL),
('2026-06-03', '14:10:00', 14, 'Cherry', 6.50, 4, 'ST004', 'Stone', 'OrchardFresh', 'kg', 0.00, 1.56, 27.56, 'North', 'USA', true, 'BATCH-CH01', 5, 'WH-N1', 'Short season'),
('2026-06-04', '08:30:00', 15, 'Lemon', 1.50, 20, 'ST005', 'Citrus', 'CitrusHub', 'kg', 0.00, 2.70, 32.70, 'West', 'USA', false, 'BATCH-L01', 20, 'WH-W2', 'Bulk order'),
('2026-06-04', '09:45:00', 16, 'Avocado', 2.75, 8, 'ST001', 'Exotic', 'ExoticImport', 'each', 0.00, 1.54, 23.54, 'West', 'USA', true, 'BATCH-AV01', 9, 'WH-W1', 'Ripe ready'),
('2026-06-04', '12:00:00', 17, 'Plum', 2.40, 10, 'ST002', 'Stone', 'OrchardFresh', 'kg', 8.00, 1.99, 25.99, 'South', 'USA', false, 'BATCH-PL01', 7, 'WH-S1', NULL),
('2026-06-04', '13:30:00', 18, 'Raspberry', 5.00, 3, 'ST003', 'Berry', 'BerryBest', 'box', 0.00, 0.90, 15.90, 'East', 'USA', true, 'BATCH-R01', 2, 'WH-E1', 'Fragile handle'),
('2026-06-05', '10:00:00', 19, 'Guava', 1.95, 14, 'ST004', 'Tropical', 'TropicSupply', 'kg', 0.00, 2.18, 29.48, 'North', 'USA', false, 'BATCH-GV01', 11, 'WH-N1', NULL),
('2026-06-05', '15:20:00', 20, 'Dragonfruit', 7.00, 2, 'ST005', 'Exotic', 'ExoticImport', 'each', 0.00, 0.84, 14.84, 'West', 'USA', true, 'BATCH-DF01', 8, 'WH-W2', 'Specialty item');
