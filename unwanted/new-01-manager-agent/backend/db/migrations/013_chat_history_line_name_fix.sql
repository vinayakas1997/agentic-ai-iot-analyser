-- Fix: chat_history is missing columns that 003_manager_tables_fresh.sql
-- tried to add via CREATE TABLE IF NOT EXISTS (no-op because table already
-- existed from 001_initial.sql).

ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS line_name TEXT;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS node TEXT;

CREATE INDEX IF NOT EXISTS idx_chat_history_line_name ON chat_history(line_name);
