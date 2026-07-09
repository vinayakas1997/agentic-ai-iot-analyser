# Database Table Design Plan

**Date:** 2026-07-09  
**Status:** Design review — multi-user, multi-session analysis

---

## Table Summary

| Table Name | Column Names | Purpose | Multi-support Evidence |
|---|---|---|---|
| `users` | `id`, `email`, `password_hash`, `created_at` | User authentication and account management | UUID PK, unique email constraint |
| `events` | `id`, `event_id`, `topic`, `user_id`, `session_id`, `payload`, `status`, `consumed_by`, `attempt`, `execute_at`, `created_at`, `updated_at` | Asynchronous job queue for background task processing | `user_id` + `session_id` columns, indexed on `user_id` |
| `results` | `id`, `user_id`, `session_id`, `event_id`, `task`, `result`, `status`, `created_at` | Persists output from completed tasks (query results, analysis) | `user_id` + `session_id` columns, indexed on `(user_id, created_at DESC)` |
| `chat_history` | `id`, `user_id`, `session_id`, `line_name`, `role`, `content`, `node`, `turn_index`, `ui_snapshot`, `schema_snapshot`, `created_at` | Stores conversation messages with per-turn UI/schema snapshots | `user_id` + `session_id` columns, composite index `(user_id, session_id)` |
| `global_registry` | `id`, `line_name`, `dataset_name`, `synonyms`, `description`, `source_type`, `source_config`, `column_definitions`, `role`, `join_hints`, `suggested_aims`, `verified`, `global_version`, `status`, `maintained_by`, `created_at`, `updated_at` | Central catalog of available datasets (tables) per production line | Shared across users (correct — no `user_id` needed), unique on `(line_name, dataset_name)` |
| `task_registry` | `id`, `user_id`, `line_name`, `version`, `task_definition` | Stores versioned user-saved task definitions per line | `user_id` column, unique on `(user_id, line_name, version)` |
| `manager_sessions` | `session_id`, `user_id`, `phase`, `status`, `line_name`, `state_json`, `version`, `created_at`, `updated_at` | Persists full manager agent state for API resume and session recovery | `session_id` PK + `user_id` column, indexed on `(user_id, updated_at DESC)` |

---

## Observations

### Observation 1: Missing Indexes on `session_id` for `events` and `results`

**Tables affected:** `events`, `results`

**Issue:** Both tables have a `session_id` column but no standalone index on it. The current indexes are:
- `events`: indexed on `(status, execute_at)`, `(topic, status)`, and `(user_id)`
- `results`: indexed on `(user_id, created_at DESC)`

If a query needs to fetch all events or results for a specific session without filtering by `user_id`, PostgreSQL will perform a sequential scan on the entire table.

**Risk level:** Low. Most queries in the codebase filter by `user_id` first (which is indexed), then narrow by `session_id`. The composite index on `user_id` covers the primary access pattern.

**Recommendation (not urgent):** If session-level queries become frequent (e.g., a "session audit" feature), consider adding:
```sql
CREATE INDEX idx_events_session_id ON events(session_id);
CREATE INDEX idx_results_session_id ON results(session_id);
```

---

### Observation 2: `manager_sessions` Uses `TEXT` as Primary Key

**Table affected:** `manager_sessions`

**Issue:** The `session_id` column is `TEXT PRIMARY KEY` instead of the more conventional `UUID`. The actual values stored are UUIDs generated in Python (`str(uuid.uuid4())`), so the data type mismatch is purely a style/standardization concern.

**Trade-offs:**
| Aspect | `TEXT` (current) | `UUID` |
|---|---|---|
| Storage | ~1 byte overhead for length prefix | 16 bytes fixed |
| Index performance | Slightly slower (variable length) | Slightly faster (fixed width) |
| Readability | Raw UUID string in DB queries | Native UUID type with functions |
| Compatibility | Works everywhere | Requires `pgcrypto` extension (already enabled) |

**Risk level:** Negligible. The table stores a small number of rows per user (session history), so performance difference is insignificant.

**Recommendation (not urgent):** No change needed. If standardization is desired in the future, a migration can convert `TEXT → UUID` without breaking the application (values are already valid UUIDs).

---

## Verdict

The schema is well-designed for multi-user, multi-session workloads. Each user-scoped table correctly includes `user_id` with appropriate indexes, and the shared `global_registry` is appropriately unscoped. No blocking issues identified.
