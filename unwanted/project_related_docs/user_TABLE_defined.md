# EDAS — User Registry Tables Definition

**Purpose:** Per-user tables for the Manager Agent — local dataset copies, versioned analysis aims, and conversation history. Schema comes from [`global_registry`](new_TABLE_defined.md) on first use; users define aims separately.

**Related:** IoT catalog → [new_TABLE_defined.md](new_TABLE_defined.md) (`global_registry`)

---

## Overview

```
global_registry   →  IoT source of truth (see new_TABLE_defined.md)
schema_registry   →  per-user local copy of datasets (one row per user + line + dataset)
task_registry     →  per-user analysis aims (versioned per user + line)
chat_history      →  per-user/session manager conversation log
```

```mermaid
flowchart LR
    GlobalRegistry[global_registry IoT]
    SchemaRegistry[schema_registry per user]
    TaskRegistry[task_registry per user]
    ChatHistory[chat_history per session]
    GlobalRegistry -->|"copy on first use"| SchemaRegistry
    SchemaRegistry -->|"datasets for fetch"| Research[Research / Executor]
    TaskRegistry -->|"aims v1 v2"| Research
    ChatHistory -->|"context"| Manager[Manager Agent]
```

- IoT truth → user local schema copy → user aims (separate lifecycle)
- User never edits `global_registry`; Manager copies into `schema_registry` after line/synonym lookup
- Analysis aims live only in `task_registry` — not merged into schema rows
- **`chat_history`** stores user/agent messages per session (includes `created_at` for message order)
- **No audit columns** on registry tables (`created_by`, `creator`, etc.) — only fields needed to run analysis and sync with global

---

## Design decisions

| Topic | Decision |
|-------|----------|
| Schema shape | Mirror `global_registry` core columns (multi-dataset, `source_config` JSONB) |
| Unique key (schema) | `(user_id, line_name, dataset_name)` |
| Sync tracking | `synced_global_version` only — compare against global to detect stale copies |
| Omit locally | `synonyms`, `maintained_by`, `global_version`, IoT audit fields (`verified_by`, `verified_at`, `verified`) |
| Omit audit on user tables | No `created_by`, `creator`, `created_at`, `updated_at`, `status` |
| Optional local keep | `suggested_aims`, `description`, `role`, `join_hints` |
| Task table | Keep **`task_registry`** separate; friendly names live in `task_definition` JSON only |
| Unique key (task) | `(user_id, line_name, version)` |
| User identity | `user_id` only — no separate `creator` column |

---

## Table 1 — schema_registry (upgraded)

**Purpose:** Local per-user copy of dataset definitions for a line. One row per dataset (e.g. `production`, `errors`). Populated by copying from `global_registry` when the user first uses a line.

**Replaces** Phase-1 shape in `edas/db/migrations/002_manager_registries.sql` (one row per `line_name`, flat `table_name` / `file_path` columns).

```sql
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
```

### Column reference

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL | Internal PK |
| `user_id` | TEXT NOT NULL | Owner of this local copy |
| `line_name` | TEXT NOT NULL | Canonical line id (resolved from global lookup) |
| `dataset_name` | TEXT NOT NULL | Logical dataset, e.g. `production`, `errors` |
| `description` | TEXT | Optional; copied from global |
| `source_type` | TEXT NOT NULL | `pg` / `csv` / `api` |
| `source_config` | JSONB NOT NULL | Connection and fetch details (same shape as global) |
| `column_definitions` | JSONB NOT NULL | Column metadata for this dataset |
| `role` | TEXT | Optional: `primary`, `errors`, `reference` |
| `join_hints` | JSONB | Optional; may be empty |
| `suggested_aims` | JSONB | Optional IoT hints copied read-only |
| `synced_global_version` | INT NOT NULL DEFAULT 1 | `global_version` from global row at last copy/sync |

**Unique constraint:** `(user_id, line_name, dataset_name)`

### Columns not stored locally

| Column / topic | Reason |
|----------------|--------|
| `synonyms` | Line already resolved before copy |
| `global_version` | Stored as `synced_global_version` |
| `maintained_by`, `verified`, `verified_by`, `verified_at` | IoT audit — stays on global only |
| `created_by`, `created_at`, `updated_at`, `status` | Unnecessary on user copy |

### JSONB structures

Same shapes as [`new_TABLE_defined.md`](new_TABLE_defined.md):

- **`source_config`** — e.g. `{ "url": "postgresql://...", "schema": "production", "table": "am307b_production" }`
- **`column_definitions`** — array of `{ name, meaning, datatype, format, nullable }`
- **`join_hints`** — optional; `null` or `{}` when empty
- **`suggested_aims`** — optional array of strings

Short example:

```json
{
  "source_config": {
    "url": "postgresql://user:pass@192.168.1.50:5432/plant_db",
    "schema": "production",
    "table": "am307b_production"
  }
}
```

### Copy rule (from global_registry)

When `(user_id, line_name)` has no local schema rows:

1. Load all active rows from `global_registry` WHERE `line_name = :matched_line`.
2. For each global row, INSERT or UPDATE local `schema_registry`:

```
user_id                 ← :user_id
line_name               ← global.line_name
dataset_name            ← global.dataset_name
description             ← global.description
source_type             ← global.source_type
source_config           ← global.source_config
column_definitions      ← global.column_definitions
role                    ← global.role
join_hints              ← global.join_hints
suggested_aims          ← global.suggested_aims
synced_global_version   ← global.global_version
```

Re-sync: if `global.global_version` > local `synced_global_version`, refresh that dataset row and update `synced_global_version`.

---

## Table 2 — task_registry

**Purpose:** User analysis aims for a line. Each new or revised definition creates a new version row. Only aims and related metadata — no schema, no audit columns.

```sql
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
```

### Column reference

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL | Internal PK |
| `user_id` | TEXT NOT NULL | Owner of this analysis definition |
| `line_name` | TEXT NOT NULL | Line this analysis applies to |
| `version` | INT NOT NULL DEFAULT 1 | User analysis revision: 1, 2, 3… |
| `task_definition` | JSONB NOT NULL | Confirmed aims, optional alias, notes (see below) |

**Unique constraint:** `(user_id, line_name, version)`

### Removed from Phase 1 (unnecessary)

| Column | Reason |
|--------|--------|
| `creator` | Redundant with `user_id` |
| `alias_name` | Use `task_definition.alias_name` instead |
| `status` | Not required for MVP |
| `created_at`, `updated_at` | Audit — not required for MVP |

### task_definition JSONB structure

```json
{
  "aims": [
    "analyze defect rate per shift",
    "identify peak failure hours"
  ],
  "alias_name": "Q2 defect study",
  "notes": "optional context from conversation"
}
```

### Version semantics

| Field | Table | Meaning |
|-------|-------|---------|
| `synced_global_version` | `schema_registry` | IoT schema revision at last copy |
| `version` | `task_registry` | User analysis revision (independent of global) |

First confirmed analysis for a user + line → `version = 1`. User adds or changes aims → insert new row with `version = max + 1`. Old versions are retained.

---

## Table 3 — chat_history

**Purpose:** Full conversation log between user and Manager Agent. Stored per user + session. Used for multi-turn context and resuming sessions.

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
CREATE INDEX idx_chat_user_session       ON chat_history(user_id, session_id);
```

### Column reference

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL | Internal PK |
| `user_id` | TEXT NOT NULL | Which user |
| `session_id` | TEXT NOT NULL | Multi-turn session id |
| `line_name` | TEXT | Machine/line being discussed |
| `role` | TEXT NOT NULL | `user` or `agent` |
| `content` | TEXT NOT NULL | Message text |
| `node` | TEXT | Optional LangGraph node name (debugging) |
| `created_at` | TIMESTAMPTZ | Message timestamp (required for ordering) |

### Example row

| user_id | session_id | line_name | role | content | node |
|---------|------------|-----------|------|---------|------|
| `user_001` | `sess-abc` | `AM307B` | `user` | `I want defect rate per shift` | `discuss_task` |
| `user_001` | `sess-abc` | `AM307B` | `agent` | `Which shift range should we use?` | `discuss_task` |

---

## User lookup flow (global + local)

```mermaid
flowchart TD
    UserInput[User says line name] --> GlobalResolve[Resolve line_name in global_registry]
    GlobalResolve -->|miss| NotFound[Line not registered]
    GlobalResolve -->|hit| LocalSchema{schema_registry rows for user_id + line?}
    LocalSchema -->|miss| CopyGlobal[Copy all datasets from global]
    LocalSchema -->|hit| TaskCheck{task_registry versions for user_id + line?}
    CopyGlobal --> TaskCheck
    TaskCheck -->|none| NewAims[Discuss new aims]
    TaskCheck -->|exists| KnownLine[Use / extend / fresh aims flow]
    NewAims --> SaveTask[Insert task_registry next version]
    KnownLine --> SaveTask
    SaveTask --> Handoff[Research payload: all schema rows + task_definition]
```

### Steps

1. User provides any name → resolve canonical `line_name` via `global_registry` (`line_name` or `synonyms`).
2. Check `schema_registry` for any rows with `(user_id, line_name)`.
3. On miss → copy all global datasets for that line into `schema_registry` for that `user_id`.
4. Check `task_registry` for `(user_id, line_name)` ordered by `version` DESC.
5. Discuss aims → insert new `task_registry` row with next `version`.
6. Handoff payload = all `schema_registry` rows for user + line + selected `task_definition`.

### SQL snippets

**Local schema exists?**

```sql
SELECT COUNT(*) AS dataset_count
FROM schema_registry
WHERE user_id = :user_id
  AND line_name = :line_name;
```

**Load all local datasets for a user + line:**

```sql
SELECT *
FROM schema_registry
WHERE user_id = :user_id
  AND line_name = :line_name
ORDER BY dataset_name;
```

**List task versions for a user + line:**

```sql
SELECT id, version, task_definition
FROM task_registry
WHERE user_id = :user_id
  AND line_name = :line_name
ORDER BY version DESC;
```

---

## Example data — user_001, line AM307B

### schema_registry (two rows, copied from global)

| user_id | line_name | dataset_name | synced_global_version |
|---------|-----------|--------------|----------------------|
| `user_001` | `AM307B` | `production` | `1` |
| `user_001` | `AM307B` | `errors` | `1` |

Each row includes full `source_config`, `column_definitions`, `role`, `join_hints` as copied from global (see examples in [new_TABLE_defined.md](new_TABLE_defined.md)).

### task_registry (one row, v1)

| user_id | line_name | version | task_definition |
|---------|-----------|---------|-----------------|
| `user_001` | `AM307B` | `1` | `{"aims": ["defect rate per shift", "peak failure hours"], "alias_name": "Shift defect study", "notes": "Q2 review"}` |

---

## Delta from current implementation

| Area | Current (`002_manager_registries.sql`, `edas/db/models.py`, `edas/agents/manager/db.py`) | Planned (this doc) |
|------|------|--------|
| `schema_registry` | One row per `line_name`; flat `table_name` / `file_path` | Multi-row per `(user_id, line_name, dataset_name)`; `source_config` JSONB |
| `schema_registry` | Audit columns (`created_by`, `verified_*`, timestamps) | Lean: data + `synced_global_version` only |
| `task_registry` | `creator`, `alias_name`, `status`, timestamps | Lean: `user_id`, `line_name`, `version`, `task_definition` |
| `task_registry` | UNIQUE `(line_name, version)` | UNIQUE `(user_id, line_name, version)` |
| Manager | `fetch_schema(line_name)` single row | Future: `fetch_schemas(user_id, line_name)` list |

---

## Out of scope — Phase B (follow-up)

- IoT seed script for `global_registry`
- Manager changes in `edas/agents/manager/db.py` and `nodes.py` (global lookup, copy-to-local, chat persist)
- Fix `smoke_test.py` for new schema shapes
- API / worker / frontend integration

**Phase A (shipped):** migration `003_manager_tables_fresh.sql` + SQLAlchemy models in `edas/db/models.py`.

---

*Last updated: 2026-06-19*
