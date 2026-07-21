-- Optimistic concurrency: add version column to manager_sessions

ALTER TABLE manager_sessions ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Add a unique constraint on (session_id, version) for optimistic locking safety
-- The primary key is already unique, but this makes the intent explicit
CREATE INDEX IF NOT EXISTS idx_manager_sessions_version ON manager_sessions(session_id, version);
