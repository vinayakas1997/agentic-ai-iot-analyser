-- Session mode for pipeline stage visualization (ask/man/plan/exe)

ALTER TABLE manager_sessions ADD COLUMN IF NOT EXISTS mode VARCHAR(10) NOT NULL DEFAULT 'ask';
CREATE INDEX IF NOT EXISTS idx_manager_sessions_mode ON manager_sessions(mode);
