ALTER TABLE global_registry
  ADD COLUMN IF NOT EXISTS data_earliest_ts TIMESTAMPTZ;
