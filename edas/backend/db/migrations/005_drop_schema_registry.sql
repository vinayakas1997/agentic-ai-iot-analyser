-- Remove local schema_registry; global_registry is the sole schema source.

DROP TABLE IF EXISTS schema_registry CASCADE;
