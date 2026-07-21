# EDAS — Database Definition
# Event Driven Analysis System — Complete Table & Column Reference

---

## Overview

```
edas (PostgreSQL database)
│
├── events              → message bus (core of EDA)
├── task_registry       → known machines / lines + analysis versions
├── schema_registry     → data source definitions per machine
├── results             → final analysis outputs per user
└── chat_history        → conversation log per user/session
```

---

## Table 1 — events
**Purpose**: The message bus. Every agent communication goes through here.
Every topic, every user task, every retry, every result — all are events.

```sql
CREATE TABLE events (
    id            SERIAL          PRIMARY KEY,
    event_id      UUID            DEFAULT gen_random_uuid() UNIQUE,
    topic         TEXT            NOT NULL,
    user_id       TEXT            NOT NULL,
    session_id    TEXT,
    payload       JSONB           NOT NULL,
    status        TEXT            DEFAULT 'pending',
    consumed_by   TEXT,
    attempt       INT             DEFAULT 0,
    execute_at    TIMESTAMPTZ     DEFAULT NOW(),
    created_at    TIMESTAMPTZ     DEFAULT NOW(),
    updated_at    TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX idx_events_topic       ON events(topic);
CREATE INDEX idx_events_user_id     ON events(user_id);
CREATE INDEX idx_events_status      ON events(status);
CREATE INDEX idx_events_execute_at  ON events(execute_at);
```

| Column | Type | Purpose |
|---|---|---|
| `id` | SERIAL | internal auto increment PK |
| `event_id` | UUID | globally unique event identifier |
| `topic` | TEXT | routing key — which agent handles this |
| `user_id` | TEXT | which user triggered this event |
| `session_id` | TEXT | which session within that user |
| `payload` | JSONB | actual message data (flexible per topic) |
| `status` | TEXT | `pending` / `running` / `done` / `failed` |
| `consumed_by` | TEXT | which agent instance picked this up |
| `attempt` | INT | retry counter — max 3 before failed |
| `execute_at` | TIMESTAMPTZ | scheduled time — immediate or future |
| `created_at` | TIMESTAMPTZ | when event was created |
| `updated_at` | TIMESTAMPTZ | last status change |

**Status flow:**
```
pending → running → done
                 → failed (attempt >= 3)
```

**Topics used:**
| Topic | Payload Keys | Flow |
|---|---|---|
| `task.new` | line_name, user_message | User → Manager Agent |
| `research.start` | line_name, schema, analysis_aims | Manager → Research Agent |
| `research.verify_schema` | line_name, schema | Manager → Research Agent |
| `manager.schema_verified` | verified, error | Research Agent → Manager |
| `executor.run` | query_type, query, source, attempt | Research → Executor |
| `research.result` | query, result, attempt | Executor → Research Agent |
| `research.retry` | query, error, attempt | Executor → Research Agent |
| `manager.result` | line_name, aims, results_summary | Research → Manager |
| `task.complete` | line_name, user_id, final_answer | Manager → DB + Frontend |
| `task.failed` | line_name, user_id, reason | Manager → DB + Frontend |

---

## Table 2 — task_registry
**Purpose**: Stores known machines/lines and their analysis definitions.
Every time a new analysis is defined for a machine, a new version is created.
Old versions are never deleted — full audit trail.

```sql
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
```

| Column | Type | Purpose |
|---|---|---|
| `id` | SERIAL | internal PK |
| `line_name` | TEXT | machine/line identifier e.g. `AM307B` |
| `alias_name` | TEXT | human friendly name e.g. `Assembly Line 3` |
| `creator` | TEXT | user_id who defined this version |
| `version` | INT | version number, increments per new definition |
| `task_definition` | JSONB | full analysis definition (see structure below) |
| `status` | TEXT | `active` / `archived` / `draft` |
| `created_at` | TIMESTAMPTZ | when this version was created |
| `updated_at` | TIMESTAMPTZ | last update |

**task_definition JSONB structure:**
```json
{
  "aims": [
    "analyze defect rate per shift",
    "identify peak failure hours",
    "compare output vs target"
  ],
  "schema": {
    "source_type": "pg",
    "table_name": "am307b_production",
    "columns": [...]
  },
  "suggested_queries": [
    "SELECT shift, COUNT(*) as defects FROM am307b_production WHERE status='fail' GROUP BY shift",
    "SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) FROM am307b_production GROUP BY hour"
  ],
  "created_at": "2026-06-18T10:00:00Z",
  "notes": "Added after Q2 review meeting"
}
```

---

## Table 3 — schema_registry
**Purpose**: Stores data source definitions per machine/line.
Before any analysis can happen, the Manager Agent needs to know
where the data is, what tables/files exist, and what each column means.

```sql
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
```

| Column | Type | Purpose |
|---|---|---|
| `id` | SERIAL | internal PK |
| `line_name` | TEXT | links to task_registry.line_name |
| `source_type` | TEXT | `csv` / `pg` / `api` |
| `table_name` | TEXT | pg table name (if source_type = pg) |
| `file_path` | TEXT | file path (if source_type = csv) |
| `column_definitions` | JSONB | full column metadata (see below) |
| `verified` | BOOLEAN | TRUE only after Research Agent confirms |
| `verified_by` | TEXT | which agent/user verified |
| `verified_at` | TIMESTAMPTZ | when verification happened |
| `created_by` | TEXT | user_id who submitted schema |
| `created_at` | TIMESTAMPTZ | first submission |
| `updated_at` | TIMESTAMPTZ | last update |

**column_definitions JSONB structure:**
```json
[
  {
    "name":     "timestamp",
    "meaning":  "time when the part was produced",
    "datatype": "timestamp",
    "format":   "YYYY-MM-DD HH:MM:SS",
    "nullable": false
  },
  {
    "name":     "part_id",
    "meaning":  "unique identifier for each produced part",
    "datatype": "text",
    "format":   "AM307B-XXXXX",
    "nullable": false
  },
  {
    "name":     "status",
    "meaning":  "pass or fail result of quality check",
    "datatype": "text",
    "format":   "pass | fail",
    "nullable": false
  },
  {
    "name":     "shift",
    "meaning":  "which shift produced this part (morning/evening/night)",
    "datatype": "text",
    "format":   "morning | evening | night",
    "nullable": true
  },
  {
    "name":     "operator_id",
    "meaning":  "ID of the operator on duty",
    "datatype": "text",
    "format":   null,
    "nullable": true
  }
]
```

---

## Table 4 — results
**Purpose**: Permanent storage of all completed analysis results per user.
DB Subscriber writes here when topic = task.complete arrives on the bus.
Used by frontend to show history and by users to retrieve past analyses.

```sql
CREATE TABLE results (
    id              SERIAL          PRIMARY KEY,
    result_id       UUID            DEFAULT gen_random_uuid() UNIQUE,
    user_id         TEXT            NOT NULL,
    session_id      TEXT,
    event_id        UUID,
    line_name       TEXT,
    analysis_aims   JSONB,
    query_results   JSONB,
    final_answer    TEXT,
    status          TEXT            DEFAULT 'complete',
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX idx_results_user_id   ON results(user_id);
CREATE INDEX idx_results_line_name ON results(line_name);
CREATE INDEX idx_results_status    ON results(status);
```

| Column | Type | Purpose |
|---|---|---|
| `id` | SERIAL | internal PK |
| `result_id` | UUID | globally unique result identifier |
| `user_id` | TEXT | which user this result belongs to |
| `session_id` | TEXT | which session produced this result |
| `event_id` | UUID | links back to originating event |
| `line_name` | TEXT | which machine was analyzed |
| `analysis_aims` | JSONB | list of aims that were analyzed |
| `query_results` | JSONB | raw results from each query |
| `final_answer` | TEXT | Manager Agent's final summary text |
| `status` | TEXT | `complete` / `partial` / `failed` |
| `created_at` | TIMESTAMPTZ | when result was saved |

**query_results JSONB structure:**
```json
[
  {
    "aim":    "analyze defect rate per shift",
    "query":  "SELECT shift, COUNT(*) as defects...",
    "result": [
      {"shift": "morning", "defects": 12},
      {"shift": "evening", "defects": 8},
      {"shift": "night",   "defects": 21}
    ],
    "status": "success"
  },
  {
    "aim":    "identify peak failure hours",
    "query":  "SELECT EXTRACT(HOUR FROM...",
    "result": [...],
    "status": "success"
  }
]
```

---

## Table 5 — chat_history
**Purpose**: Full conversation log between user and Manager Agent.
Stored per user + session. Used to maintain context in multi-turn
conversations and to resume where the user left off.

```sql
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
```

| Column | Type | Purpose |
|---|---|---|
| `id` | SERIAL | internal PK |
| `user_id` | TEXT | which user |
| `session_id` | TEXT | which session |
| `line_name` | TEXT | which machine being discussed |
| `role` | TEXT | `user` / `agent` |
| `content` | TEXT | actual message text |
| `node` | TEXT | which LangGraph node sent this (for debugging) |
| `created_at` | TIMESTAMPTZ | message timestamp |

---

## Complete Entity Relationship

```
events
  user_id ──────────────────────────────┐
  session_id ───────────────────────┐   │
                                    │   │
task_registry                       │   │
  line_name (PK per version) ───┐   │   │
  creator = user_id ────────────┼───┼───┤
                                │   │   │
schema_registry                 │   │   │
  line_name → task_registry ────┘   │   │
  created_by = user_id ─────────────┼───┤
                                    │   │
results                             │   │
  session_id ───────────────────────┘   │
  user_id ───────────────────────────────┘
  event_id → events.event_id

chat_history
  user_id + session_id
  line_name → task_registry
```

---

## Summary — What Each Table Is For

| Table | One Line Purpose |
|---|---|
| `events` | The message bus — everything that happens is an event |
| `task_registry` | Known machines + their analysis definitions + versions |
| `schema_registry` | Data source info per machine — verified by Research Agent |
| `results` | Final analysis outputs — permanent per user |
| `chat_history` | Full conversation log — context for multi-turn chat |

---

## Migration File (run order)

```sql
-- 001_initial.sql

-- 1. events (bus — needed first, everything depends on it)
-- 2. task_registry
-- 3. schema_registry
-- 4. results
-- 5. chat_history
```
