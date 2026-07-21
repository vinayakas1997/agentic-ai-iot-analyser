-- Manager Agent registries (Phase 1)

CREATE TABLE task_registry (
    id              SERIAL          PRIMARY KEY,
    line_name       TEXT            NOT NULL,
    alias_name      TEXT,
    creator         TEXT            NOT NULL,
    version         INT             NOT NULL    DEFAULT 1,
    task_definition JSONB           NOT NULL,
    status          TEXT            DEFAULT 'active',
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW(),

    UNIQUE (line_name, version)
);

CREATE INDEX idx_task_registry_line_name ON task_registry(line_name);
CREATE INDEX idx_task_registry_status    ON task_registry(status);

CREATE TABLE schema_registry (
    id                  SERIAL      PRIMARY KEY,
    line_name           TEXT        NOT NULL    UNIQUE,
    source_type         TEXT        NOT NULL,
    table_name          TEXT,
    file_path           TEXT,
    column_definitions  JSONB       NOT NULL,
    verified            BOOLEAN     DEFAULT FALSE,
    verified_by         TEXT,
    verified_at         TIMESTAMPTZ,
    created_by          TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_schema_registry_line_name ON schema_registry(line_name);
CREATE INDEX idx_schema_registry_verified  ON schema_registry(verified);
