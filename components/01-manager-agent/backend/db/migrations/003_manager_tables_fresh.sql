-- Manager tables fresh setup (Phase A)
-- Supersedes Phase-1 shapes from 002_manager_registries.sql.
-- Creates 4-table manager data layer.
-- events, results, users from 001 are untouched.

CREATE TABLE IF NOT EXISTS global_registry (
    id                  SERIAL          PRIMARY KEY,
    line_name           TEXT            NOT NULL,
    dataset_name        TEXT            NOT NULL,
    synonyms            JSONB,
    description         TEXT,
    source_type         TEXT            NOT NULL,
    source_config       JSONB           NOT NULL,
    column_definitions  JSONB           NOT NULL,
    role                TEXT,
    join_hints          JSONB,
    suggested_aims      JSONB,
    verified            BOOLEAN         DEFAULT TRUE,
    global_version      INT             NOT NULL DEFAULT 1,
    status              TEXT            DEFAULT 'active',
    maintained_by       TEXT,
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     DEFAULT NOW(),

    UNIQUE (line_name, dataset_name)
);

CREATE INDEX IF NOT EXISTS idx_global_registry_line_name ON global_registry(line_name);
CREATE INDEX IF NOT EXISTS idx_global_registry_status    ON global_registry(status);
CREATE INDEX IF NOT EXISTS idx_global_registry_synonyms  ON global_registry USING GIN (synonyms);

CREATE TABLE IF NOT EXISTS schema_registry (
    id                      SERIAL          PRIMARY KEY,
    user_id                 TEXT            NOT NULL,
    line_name               TEXT            NOT NULL,
    dataset_name            TEXT            NOT NULL,
    description             TEXT,
    source_type             TEXT            NOT NULL,
    source_config           JSONB           NOT NULL,
    column_definitions      JSONB           NOT NULL,
    role                    TEXT,
    join_hints              JSONB,
    suggested_aims          JSONB,
    synced_global_version   INT             NOT NULL DEFAULT 1,

    UNIQUE (user_id, line_name, dataset_name)
);

CREATE INDEX IF NOT EXISTS idx_schema_registry_user_id   ON schema_registry(user_id);
CREATE INDEX IF NOT EXISTS idx_schema_registry_user_line ON schema_registry(user_id, line_name);

CREATE TABLE IF NOT EXISTS task_registry (
    id              SERIAL          PRIMARY KEY,
    user_id         TEXT            NOT NULL,
    line_name       TEXT            NOT NULL,
    version         INT             NOT NULL    DEFAULT 1,
    task_definition JSONB           NOT NULL,

    UNIQUE (user_id, line_name, version)
);

CREATE INDEX IF NOT EXISTS idx_task_registry_user_id   ON task_registry(user_id);
CREATE INDEX IF NOT EXISTS idx_task_registry_user_line ON task_registry(user_id, line_name);

CREATE TABLE IF NOT EXISTS chat_history (
    id          SERIAL          PRIMARY KEY,
    user_id     TEXT            NOT NULL,
    session_id  TEXT            NOT NULL,
    line_name   TEXT,
    role        TEXT            NOT NULL,
    content     TEXT            NOT NULL,
    node        TEXT,
    created_at  TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_user_id    ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_user_session       ON chat_history(user_id, session_id);
