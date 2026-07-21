# EDAS — global_registry Table Definition

**Purpose:** IoT-owned catalog of machines/lines and their data sources. The IoT team maintains this table. Each row describes one dataset (table/file) for a line, including how to connect and fetch data and what each column means.

---

## Overview

```
global_registry  →  IoT source of truth (one row per line + dataset)
```

---

## Design decisions

| Topic | Decision |
|-------|----------|
| Row granularity | One row per `(line_name, dataset_name)` — a line may have multiple datasets (e.g. `production`, `errors`) |
| Alternate names | **`synonyms` JSONB only** — no separate `alias_name`; all user-facing names live in one array |
| `join_hints` | Optional — `NULL`, `{}`, or `[]` when empty or for single-table lines |
| `source_config` | JSONB with raw `url` for MVP; migrate to `connection_ref` later when security is required |
| Versioning | **`global_version`** — IoT bumps this when schema or source config changes for that row |
| Ownership | IoT team writes and updates; EDAS reads at runtime |

---

## Table — global_registry

**Purpose:** Canonical definitions for each machine/line and each connected dataset. Fetch logic uses `source_type` + `source_config`.

```sql
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
```

### Column reference

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL | Internal PK |
| `line_name` | TEXT NOT NULL | Canonical machine/line id, e.g. `AM307B` |
| `dataset_name` | TEXT NOT NULL | Logical dataset within the line, e.g. `production`, `errors` |
| `synonyms` | JSONB | Alternate names the user might type (includes friendly names and nicknames) |
| `description` | TEXT | Optional short description of this line or dataset |
| `source_type` | TEXT NOT NULL | `pg` / `csv` / `api` |
| `source_config` | JSONB NOT NULL | Connection and fetch details (see examples below) |
| `column_definitions` | JSONB NOT NULL | Column metadata for this dataset |
| `role` | TEXT | Optional: `primary`, `errors`, `reference` |
| `join_hints` | JSONB | Optional join keys to other datasets on the same line; may be empty |
| `suggested_aims` | JSONB | Optional IoT-suggested analysis hints |
| `verified` | BOOLEAN | `TRUE` when IoT has approved this row for use |
| `global_version` | INT NOT NULL DEFAULT 1 | Increments when IoT updates schema for this row |
| `status` | TEXT DEFAULT `active` | `active` / `deprecated` / `archived` |
| `maintained_by` | TEXT | IoT owner or team identifier |
| `created_at` | TIMESTAMPTZ | Row created |
| `updated_at` | TIMESTAMPTZ | Last IoT update |

**Unique constraint:** `(line_name, dataset_name)`

---

## JSONB structures

### synonyms

All alternate names in one array (no separate `alias_name` column):

```json
["AM307B", "Assembly Line 307B", "line 3", "307B"]
```

Duplicate the same `synonyms` on every row for a given `line_name`, or store only on the `role = 'primary'` row and resolve via that row first.

### source_config

**PostgreSQL (MVP — URL in JSONB):**

```json
{
  "url": "postgresql://user:password@192.168.1.50:5432/plant_db",
  "schema": "production",
  "table": "am307b_production"
}
```

**CSV:**

```json
{
  "url": "file:///data/am307b/production.csv"
}
```

Or:

```json
{
  "path": "am307b/production.csv"
}
```

**Future (security):** replace `"url"` with `"connection_ref": "IOT_PG_PLANT1"` resolved from env/vault — same column, no table redesign.

### column_definitions

```json
[
  {
    "name": "timestamp",
    "meaning": "time when the part was produced",
    "datatype": "timestamp",
    "format": "YYYY-MM-DD HH:MM:SS",
    "nullable": false
  },
  {
    "name": "part_id",
    "meaning": "unique identifier for each produced part",
    "datatype": "text",
    "format": "AM307B-XXXXX",
    "nullable": false
  },
  {
    "name": "status",
    "meaning": "pass or fail result of quality check",
    "datatype": "text",
    "format": "pass | fail",
    "nullable": false
  }
]
```

### join_hints

Optional. Empty is valid for single-table lines or when joins are unknown.

**Empty:**

```json
null
```

or

```json
{}
```

**With joins:**

```json
{
  "joins": [
    {
      "to_dataset": "errors",
      "on": [{ "from": "part_id", "to": "part_id" }]
    }
  ]
}
```

### suggested_aims

Optional IoT hints:

```json
["defect rate per shift", "peak failure hours"]
```

---

## Lookup (within global_registry)

User input (e.g. `"line 3"`) is resolved to a canonical `line_name`, then all datasets for that line are loaded.

```mermaid
flowchart TD
    UserInput[User says line name] --> GlobalLookup[Match line_name or synonyms]
    GlobalLookup -->|hit| LoadDatasets[Fetch all rows for line_name]
    GlobalLookup -->|miss| NotFound[Line not in global_registry]
    LoadDatasets --> Ready[All datasets + columns available]
```

### Steps

1. User provides any name (e.g. `"line 3"`).
2. Match against `line_name` or `synonyms` in `global_registry`.
3. On hit, resolve canonical `line_name` and fetch **all rows** for that line (every `dataset_name`).
4. On miss, line is not registered — IoT must add it.

### SQL lookup

```sql
-- Step 1: resolve line_name from user input
SELECT DISTINCT line_name
FROM global_registry
WHERE status = 'active'
  AND (
    line_name = :user_input
    OR lower(line_name) = lower(:user_input)
    OR synonyms @> to_jsonb(ARRAY[:user_input])
  )
LIMIT 1;

-- Step 2: load all datasets for that line
SELECT *
FROM global_registry
WHERE line_name = :matched_line_name
  AND status = 'active'
ORDER BY dataset_name;
```

---

## Example rows — line AM307B (two datasets)

### Row 1 — production (primary)

| Field | Value |
|-------|-------|
| `line_name` | `AM307B` |
| `dataset_name` | `production` |
| `synonyms` | `["AM307B", "Assembly Line 307B", "line 3", "307B"]` |
| `description` | Main production output for assembly line 307B |
| `source_type` | `pg` |
| `source_config` | `{"url": "postgresql://user:pass@192.168.1.50:5432/plant_db", "schema": "production", "table": "am307b_production"}` |
| `column_definitions` | `[{"name": "timestamp", ...}, {"name": "part_id", ...}, {"name": "status", ...}]` |
| `role` | `primary` |
| `join_hints` | `null` |
| `suggested_aims` | `["defect rate per shift", "output vs target"]` |
| `verified` | `true` |
| `global_version` | `1` |
| `status` | `active` |

### Row 2 — errors

| Field | Value |
|-------|-------|
| `line_name` | `AM307B` |
| `dataset_name` | `errors` |
| `synonyms` | `["AM307B", "Assembly Line 307B", "line 3", "307B"]` |
| `description` | Error and downtime events for line 307B |
| `source_type` | `pg` |
| `source_config` | `{"url": "postgresql://user:pass@192.168.1.50:5432/plant_db", "schema": "production", "table": "am307b_errors"}` |
| `column_definitions` | `[{"name": "part_id", ...}, {"name": "error_code", ...}, {"name": "timestamp", ...}]` |
| `role` | `errors` |
| `join_hints` | `{"joins": [{"to_dataset": "production", "on": [{"from": "part_id", "to": "part_id"}]}]}` |
| `suggested_aims` | `null` |
| `verified` | `true` |
| `global_version` | `1` |
| `status` | `active` |

---

## global_version

| Field | Meaning |
|-------|---------|
| `global_version` | IoT bumps when `source_config`, `column_definitions`, or other schema fields change for that row |

When IoT publishes an update, increment `global_version` and set `updated_at`. Consumers can compare version to detect stale cached copies.

---

*Last updated: 2026-06-19*
