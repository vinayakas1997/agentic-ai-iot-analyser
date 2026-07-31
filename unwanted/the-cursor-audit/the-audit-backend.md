## Backend audit (multi-user LAN: app server + DGX)

Scope: verified issues in `api.py`, `config.py`, `user_datasets.py`, `registry_admin.py`, `llm_client.py`, `sql_executor.py`, `sqlite_importer.py`, `docker-entrypoint.sh`, nginx/compose. `list_sessions` empty-`user_id` leak is **already fixed** (returns `[]`); related fallback patterns remain elsewhere.

---

### Critical

| # | Severity | File | What the code does | Why it matters |
|---|----------|------|--------------------|----------------|
| 1 | **Critical** | `api.py` (`upload_csv`, `get_user_datasets`, `confirm_upload`, `llm_fill_upload`, `patch_dataset_columns`, `remove_user_dataset`); `config.py` `default_user_id="98765"` | Empty/missing `user_id` becomes `settings.default_user_id`. Uploads land in `/data/users/98765/data.db` and `user_registry` rows for that ID. | On LAN, any client that omits `user_id` (bug, old client, or curl) **shares one CSV store**. Users silently read/overwrite each other’s personal datasets. |
| 2 | **Critical** | `api.py` `create_session` | `uid = (body.user_id or settings.default_user_id)` | Sessions without `user_id` all attach to `98765`, so titles/turns/query results mix under one owner and show up in that user’s session list. |
| 3 | **Critical** | `api.py` `send_message` | `MessageRequest` has **no** `user_id`. Loads session by `session_id` only; uses `session.user_id` for personal datasets; writes turns/results with no ownership check. | Knowing/guessing a UUID lets another LAN user **run analysis on the owner’s uploaded CSVs**, append chat history, and get query rows back—while `GET /sessions/{id}` still requires ownership. Classic IDOR. |
| 4 | **Critical** | `api.py` `login` + all `user_id` query/body params | Login is “any string → role”; IoT list only flips `role`. No password, token, or server session. Clients send `user_id` on each call. | On a shared LAN, **impersonation is trivial**: send victim’s ID and pass `_get_session_owned` / dataset filters. Isolation is honor-system, not auth. |

---

### High

| # | Severity | File | What the code does | Why it matters |
|---|----------|------|--------------------|----------------|
| 5 | **High** | `registry_admin.py` `confirm_entry` / `delete_entry`; `api.py` registry routes | Ownership: `if user_id and row.maintained_by and row.maintained_by != user_id`. Empty `user_id` **skips** the check. | Confirm/delete any global_registry entry (including others’ drafts) by omitting `user_id`. |
| 6 | **High** | `api.py` `/registry-admin/*` | No IoT-role gate. Introspect/create/list/delete are open to anyone who can hit the API. | Normal users (or spoofed IDs) can **sample any public PG table**, register datasets, and mutate the shared catalog that all users query. |
| 7 | **High** | `registry_admin.py` `list_entries`; `api.py` `registry_list_entries` | `maintained_by=""` → `list_entries(None)` → **all** registry rows (draft + active, all maintainers). | Cross-user leak of draft IoT registrations and full column metadata. |
| 8 | **High** | `api.py` `bucket_proceed`, `execute_query`, `get_session_progress` | No `user_id` / ownership. `bucket_proceed` only needs `session_id`. Progress store is keyed by `session_id` only. | Proceed/task write and progress peek without proving ownership; progress can leak step/detail text for in-flight work. |
| 9 | **High** | `registry_admin.py` `introspect_pg_table` | `text(f'SELECT * FROM "{table_name}" LIMIT 5')` with client-supplied `table_name`. | A `"` in `table_name` can break identifier quoting → **SQL injection** against the shared DGX Postgres (read/side effects depending on DB role). |
| 10 | **High** | `sqlite_importer.py` `user_db_path` | `os.path.join(user_data_dir, user_id)` with no sanitization. | `user_id` like `../other_user` or `..` segments can write SQLite **outside** the intended volume / into another user’s tree on the app-server volume. |

---

### Medium

| # | Severity | File | What the code does | Why it matters |
|---|----------|------|--------------------|----------------|
| 11 | **Medium** | `llm_client.py` `language_instruction` | Only `"en"` (empty) and `"ja"`. Unknown codes → `""`. | Non-JA UI languages get **no** language constraint; model defaults to English. Weak for JP/EN LAN rollout beyond those two. |
| 12 | **Medium** | `llm_client.py` `summarize_turns`; `api.py` SQL-retry prompt in `_handle_direct` (~1084–1091) | Summaries and the “SQL-only retry” prompt omit `language_instruction`. | Japanese sessions still get English summaries / retry text (when those paths run). |
| 13 | **Medium** | `api.py` `upload_csv` + `csv_validator.validate_csv` | Full body `await f.read()` **before** size check. Nginx caps 50m on `:7008`; compose also publishes **`:7010`**. | Direct hits to backend bypass nginx body limit → large uploads buffered in memory → DoS/OOM on the app server. |
| 14 | **Medium** | `frontend/nginx.conf` | No `proxy_read_timeout`; LLM timeout is 120s (`config.py`). | Nginx default ~60s can cut long FOCUS/LLM calls between app server and DGX vLLM → flaky multi-user load. |
| 15 | **Medium** | `docker-compose.dgx.yml` + `docker-compose.app.yml` | PG `5432:5432` on all interfaces; default `manager_agent_pass`; backend `7010:7010` public; vLLM via `DGX_HOST`. | LAN peers can talk to Postgres/vLLM/API directly if firewall isn’t locked. Compose comments admit this; defaults make it easy to leave open. |
| 16 | **Medium** | `api.py` `_handle_focus_multi`; `execute_query` | Multi-aim path and `/execute-query` call Postgres `execute_sql` only—not `focus_agent`’s SQLite router. | Personal CSV datasets break or hit the wrong DB when multiple aims or the execute-query path are used. |
| 17 | **Medium** | `sql_executor.validate_sql` vs `validate_sql_safety` | Live path uses `validate_sql` (no CROSS JOIN / schema-qualify checks). Stricter checks only in aims critic path. | FOCUS/agent SQL can still CROSS JOIN or touch unexpected tables; weaker guard on the hot path. |

---

### Low / inefficiency (verified)

| # | Severity | File | What the code does | Why it matters |
|---|----------|------|--------------------|----------------|
| 18 | **Low** | `api.py` `_build_context` → `_fetch_sample_rows` | One sample query **per attached dataset** per message. | N+1 round-trips to PG/SQLite under concurrent LAN users. |
| 19 | **Low** | `api.py` `list_sessions` | `select(ManagerSession)` loads full rows (incl. heavy `state_json`) then returns metadata only. | Unnecessary I/O/memory as sessions grow (full result rows in JSONB). |
| 20 | **Low** | `api.py` message save + `get_session` | Persists full `rows` in `chat_query_results`; GET returns whole `state`. | DB and responses balloon; reload/list pressure on app server ↔ DGX DB link. |
| 21 | **Low** | `api.py` `_progress_store` | In-memory dict; keys never pruned per session lifecycle. | Multi-worker/restart inconsistency; unbounded growth for many session IDs. |
| 22 | **Low** | `api.py` routing | `/messages` only dispatches `suggest` or `focus` (`direct` handler unused). | Dead path / confusing ops; not a cross-user leak by itself. |
| 23 | **Info** | `docker-entrypoint.sh` | Runs `init_db` then `exec "$@"`. | Fine for single backend; concurrent multi-replica init is a race (not present in current compose). |

---

### Auth model (ID-only allowlist) — implications

```894:899:c:\Users\106761\Desktop\agentic-ai-iot-analyser\agentic-project\backend\api.py
@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Stateless ID-only allowlist check — no passwords. Decides which top-level view the
    frontend renders (IoT registration page vs the normal dashboard)."""
    role = "iot" if req.user_id.strip().lower() in settings.get_iot_user_ids() else "normal"
    return LoginResponse(user_id=req.user_id.strip(), role=role)
```

- **Any** ID logs in; IoT JSON only chooses UI/role, and **backend does not enforce** that role on registry-admin.
- Ownership checks compare **client-supplied** `user_id` to DB rows → spoofing equals access.
- Fit for a trusted lab demo; **not** fit for hostile or curious multi-user LAN without network ACLs + real auth.

---

### Already OK (for the focus areas)

- `list_sessions`: empty `user_id` → `[]` (no all-users dump).
- `get_session` / `delete_session` / `update_session` / `summarize_context`: use `_get_session_owned` (requires non-empty matching `user_id`)—still spoofable under ID-only auth.
- `user_datasets.py` mutations filter `UserRegistry.id` **and** `user_id` (good once `user_id` is correct and not defaulted).
- Nginx `client_max_body_size 50m` matches `max_upload_size_mb` for the frontend proxy path only.

---

### Highest-priority fixes (for LAN)

1. Reject empty `user_id` everywhere (no `default_user_id` fallback for uploads/sessions/datasets).  
2. Require `user_id` + ownership on `/messages`, `bucket_proceed`, progress, and registry mutations; enforce IoT role server-side.  
3. Treat empty `user_id` on registry confirm/delete as **deny**, not allow.  
4. Sanitize `user_id` / `table_name`; stop quoting raw identifiers in SQL.  
5. Don’t publish `:7010` / `:5432` to the whole LAN; add nginx LLM proxy timeouts; cap upload size before full buffering.