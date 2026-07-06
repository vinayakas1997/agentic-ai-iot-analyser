-- EDAS initial schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE events (
    id            SERIAL PRIMARY KEY,
    event_id      UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    topic         TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    session_id    TEXT,
    payload       JSONB NOT NULL,
    status        TEXT DEFAULT 'pending',
    consumed_by   TEXT,
    attempt       INT DEFAULT 0,
    execute_at    TIMESTAMPTZ DEFAULT NOW(),
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_pending ON events (status, execute_at) WHERE status = 'pending';
CREATE INDEX idx_events_topic_status ON events (topic, status);
CREATE INDEX idx_events_user_id ON events (user_id);

CREATE TABLE results (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    session_id  TEXT,
    event_id    UUID,
    task        TEXT,
    result      JSONB,
    status      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_results_user_created ON results (user_id, created_at DESC);

CREATE TABLE chat_history (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    session_id  TEXT,
    role        TEXT,
    content     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_user_session ON chat_history (user_id, session_id);
