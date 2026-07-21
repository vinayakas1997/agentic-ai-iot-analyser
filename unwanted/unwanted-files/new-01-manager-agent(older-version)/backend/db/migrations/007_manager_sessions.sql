-- Manager session state persistence for API / frontend resume.

CREATE TABLE IF NOT EXISTS manager_sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    phase       TEXT NOT NULL DEFAULT 'extract',
    status      TEXT NOT NULL DEFAULT 'active',
    line_name   TEXT,
    state_json  JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_manager_sessions_user ON manager_sessions(user_id, updated_at DESC);
