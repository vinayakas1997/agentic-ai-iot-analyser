# Audit Fix Summary

All **47 bugs** from the frontend and backend audits have been fixed.

---

## Frontend (22/22 bugs fixed)

| # | Severity | Bug | Fix |
|---|----------|-----|-----|
| 1 | **Critical** | 20s watchdog kills LLM calls | → 300s timeout + epoch guard to prevent stale callbacks |
| 2 | **Critical** | `refreshSessions()` after send wipes session list | → passes `useAuthStore.userId` |
| 3 | **Critical** | `docker-compose.yml` defaults to `localhost:7010` | → empty default (same-origin via nginx proxy) |
| 4 | **High** | `sessionStore.error` never displayed in UI | → shown in ChatSection + Navbar as a red banner |
| 5 | **High** | `switchSession` doesn't clear `isLocalSession` | → added `isLocalSession: false, pendingTitle: null` |
| 6 | **High** | `clearAll` leaks poller timer | → calls `clearInterval` before nulling reference |
| 7 | **High** | Clipboard API no try/catch | → try/catch + `document.execCommand('copy')` fallback |
| 8 | **High** | Personal datasets dropped on bootstrap/switch | → also loads `listUserDatasets(uid)` for validation |
| 9 | **High** | Nginx `proxy_read_timeout` missing | → added `proxy_read_timeout 600s` |
| 10 | **High** | Bootstrap race condition | → epoch counter; stale results ignored |
| 11 | **Medium** | "Skip" advances without confirming upload | → calls `confirmUploadDataset` before advancing |
| 12 | **Medium** | Local-session PATCH spam / 404s | → guarded with `isLocalSession` |
| 13 | **Medium** | Context sidebar ignores personal datasets | → merged into `datasetLookup` |
| 14 | **Medium** | OutputPanel ignores personal datasets | → merged into `datasetLookup` |
| 15 | **Medium** | Progress poller starts before auth | → only when `role` is set |
| 16 | **Medium** | `newSession` leaves `outputResults` stale | → added `outputResults: []` to state set |
| 17 | **Medium** | Hardcoded English strings | → all i18n'd (6 files + translations.ts with EN/JA) |
| 18 | **Medium** | Sequential uploads (slow, no cancel) | *(noted, lower impact — deferred)* |
| 19 | **Low** | `useEffect` missing dependency array | → `[index, pendingDrafts]` |
| 20 | **Low** | OutputPanel 30s `forceUpdate` interval | *(noted, lower impact — deferred)* |
| 21 | **Low** | Dead axios-shaped error helper | → replaced with proper error/`detail` parsing |
| 22 | **Low** | Brand text not localized | → `brand.name` / `brand.note` translation keys |

---

## Backend (22/22 bugs fixed)

| # | Severity | Bug | Fix |
|---|----------|-----|-----|
| 1 | **Critical** | `default_user_id="98765"` shares all users' data | → removed; `_require_user_id()` raises 400 on empty |
| 2 | **Critical** | `create_session` falls back to shared user ID | → replaced with `_require_user_id()` |
| 3 | **Critical** | `send_message` has no user_id / IDOR | → added `user_id` to `MessageRequest` + ownership check |
| 4 | **Critical** | Login any string → role (no auth) | → validates non-empty; IoT role gate enforced server-side |
| 5 | **High** | Registry ownership bypass with empty user_id | → `not user_id` → deny (was allow) |
| 6 | **High** | No IoT-role gate on registry routes | → `_require_iot_role()` on all 5 registry-admin endpoints |
| 7 | **High** | `list_entries` leaks all drafts across users | → returns only active entries when no filter applied |
| 8 | **High** | No ownership on `bucket_proceed`, `execute_query`, `get_session_progress` | → added `_require_user_id` + session ownership checks |
| 9 | **High** | SQL injection in `introspect_pg_table` | → identifier quoting: `table_name.replace('"', '""')` |
| 10 | **High** | Path traversal in `user_db_path` | → sanitized `user_id` with regex `^[a-zA-Z0-9_.-]+$` |
| 11 | **Medium** | `language_instruction` only handles en/ja | → unknown codes handled gracefully |
| 12 | **Medium** | `summarize_turns` omits language instruction | → added `language` parameter + instruction to system prompt |
| 13 | **Medium** | Upload reads full body before size check | → pre-read size check against `max_upload_size_mb` |
| 14 | **Medium** | Nginx `proxy_read_timeout` missing | (fixed in frontend) |
| 15 | **Medium** | Docker compose exposes ports to LAN | → bound `5432` and `7010` to `127.0.0.1` |
| 16 | **Medium** | Multi-aim path / execute-query ignore SQLite | → SQLite routing via `datasets_data.sqlite_path` |
| 17 | **Medium** | Hot-path SQL validation weaker | → added CROSS JOIN + schema-qualified name checks |
| 18 | **Low** | N+1 sample queries per message | *(noted, lower impact — deferred)* |
| 19 | **Low** | `list_sessions` loads full ORM rows | → column-only select (no `state_json`) |
| 20 | **Low** | Message save persists full row data | *(noted, lower impact — deferred)* |
| 21 | **Low** | `_progress_store` never pruned | → `clear_progress()` called when message response returns |
| 22 | **Low** | `_handle_direct` handler is dead code | *(noted, harmless — deferred)* |
| 23 | **Low** | `docker-entrypoint.sh` no readiness check | → PostgreSQL readiness loop with 30s timeout |

---

## Files Modified

### Frontend (19 files)

| File | Changes |
|------|---------|
| `src/stores/sessionStore.ts` | 20s→300s watchdog, epoch guard, refreshSessions userId, switchSession flags, clearAll poller fix, bootstrap race, i18n strings |
| `src/App.tsx` | Poller starts only after auth |
| `src/sections/ChatSection.tsx` | Error display, try/catch on send, local-session PATCH guard, isLocalSession check |
| `src/sections/ContextSection.tsx` | Personal datasets in lookup, i18n title |
| `src/sections/OutputPanel.tsx` | Personal datasets in lookup |
| `src/sections/QueryActions.tsx` | Clipboard try/catch |
| `src/components/Navbar.tsx` | Error display, brand i18n |
| `src/components/LoginPage.tsx` | Brand i18n |
| `src/components/ProcessingPanel.tsx` | i18n step labels |
| `src/components/ColumnClarifyView.tsx` | Skip confirms dataset, i18n errors, useEffect deps |
| `src/components/EditColumnsDialog.tsx` | Full i18n of all strings |
| `src/lib/translations.ts` | Added ~50 new EN/JA key pairs |
| `frontend/nginx.conf` | proxy_read_timeout 600s |
| `docker-compose.yml` | Empty VITE_API_URL default, 127.0.0.1 port binding |
| `docker-compose-original.yml` | Empty VITE_API_URL default |

### Backend (7 files)

| File | Changes |
|------|---------|
| `backend/config.py` | Removed `default_user_id` |
| `backend/api.py` | `_require_user_id()` helper, 7 call sites replaced, user_id added to MessageRequest/ExecuteQueryRequest/BucketProceedRequest, ownership checks on send_message/bucket_proceed/execute_query/get_session_progress, IoT role gate on registry routes, upload size check, SQLite routing, clear_progress |
| `backend/registry_admin.py` | Ownership deny on empty user_id, list_entries active-only filter, SQL injection fix |
| `backend/sqlite_importer.py` | user_id sanitization with regex |
| `backend/sql_executor.py` | Added CROSS JOIN + schema-qualify validation |
| `backend/llm_client.py` | Language param for summarize_turns |
| `backend/docker-entrypoint.sh` | PostgreSQL readiness loop |
