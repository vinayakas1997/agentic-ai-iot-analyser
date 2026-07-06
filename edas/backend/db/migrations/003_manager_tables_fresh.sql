-- Manager tables fresh setup (Phase A)
-- Supersedes Phase-1 shapes from 002_manager_registries.sql.
-- Drops old task_registry, schema_registry, chat_history; creates 4-table manager data layer.
-- Dev data in dropped tables will be lost. events, results, users from 001 are untouched.

DROP TABLE IF EXISTS task_registry CASCADE;
DROP TABLE IF EXISTS schema_registry CASCADE;
DROP TABLE IF EXISTS chat_history CASCADE;

CREATE TABLE global_registry (
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

CREATE INDEX idx_global_registry_line_name ON global_registry(line_name);
CREATE INDEX idx_global_registry_status    ON global_registry(status);
CREATE INDEX idx_global_registry_synonyms  ON global_registry USING GIN (synonyms);

CREATE TABLE schema_registry (
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

CREATE INDEX idx_schema_registry_user_id   ON schema_registry(user_id);
CREATE INDEX idx_schema_registry_user_line ON schema_registry(user_id, line_name);

CREATE TABLE task_registry (
    id              SERIAL          PRIMARY KEY,
    user_id         TEXT            NOT NULL,
    line_name       TEXT            NOT NULL,
    version         INT             NOT NULL    DEFAULT 1,
    task_definition JSONB           NOT NULL,

    UNIQUE (user_id, line_name, version)
);

CREATE INDEX idx_task_registry_user_id   ON task_registry(user_id);
CREATE INDEX idx_task_registry_user_line ON task_registry(user_id, line_name);

CREATE TABLE chat_history (
    id          SERIAL          PRIMARY KEY,
    user_id     TEXT            NOT NULL,
    session_id  TEXT            NOT NULL,
    line_name   TEXT,
    role        TEXT            NOT NULL,
    content     TEXT            NOT NULL,
    node        TEXT,
    created_at  TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX idx_chat_history_user_id    ON chat_history(user_id);
CREATE INDEX idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX idx_chat_user_session       ON chat_history(user_id, session_id);
