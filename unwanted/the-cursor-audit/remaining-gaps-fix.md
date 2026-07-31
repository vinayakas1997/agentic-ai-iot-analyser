# Remaining audit gaps — fix summary

Date: 2026-07-30  
Follow-up to `frontend-backend-fix.md` after verifying claimed fixes against the codebase.

---

## Why this pass was needed

Most items in `frontend-backend-fix.md` were already in the tree, but a few **critical wiring gaps** remained:

- Backend required `user_id` on `/messages` and `/sessions/{id}/progress`
- Frontend `sendMessage` / `getProgress` did **not** send `user_id` → chat/progress would fail with `400 user_id is required` after deploy
- IoT registry introspect/create also needed `user_id` for the new IoT role gate
- `execute_query` personal-CSV path treated `list_user_datasets()` (a list) as a `{datasets: ...}` dict
- Progress endpoint required `user_id` but did not verify session ownership
- `docker-compose.app.yml` still published backend `:7010` on all interfaces

---

## What was fixed in this pass

### Frontend

| Item | Change |
|------|--------|
| `sendMessage` | Accepts `userId`; sends `user_id` in POST body to `/api/v2/messages` |
| `getProgress` | Accepts `userId`; sends `?user_id=` on progress GET |
| `executeQuery` | Accepts `userId`; sends `user_id` in body |
| `introspectTable` | Sends `user_id` for IoT registry-admin gate |
| `createRegistryEntry` | Sends `user_id` (defaults to `maintained_by`) |
| `sessionStore.sendUserMessage` | Passes logged-in `userId` into `getProgress` and `sendMessage` |
| `IotRegistryPage` | Passes `userId` into introspect + create entry |

### Backend

| Item | Change |
|------|--------|
| `GET /sessions/{id}/progress` | `_require_user_id` **and** `_get_session_owned` (ownership, not just non-empty id) |
| `POST /execute-query` personal datasets | Uses `fetch_active_user_datasets(...)` (correct shape + `sqlite_path`) instead of broken `list_user_datasets` dict access |
| `language_instruction` | Unknown language codes get an explicit “respond in language `{code}`” instruction instead of silent empty string |

### Deploy / compose

| Item | Change |
|------|--------|
| `docker-compose.app.yml` | Backend port bound to `127.0.0.1:7010:7010` (LAN users use `:7008` → nginx `/api/`) |

Containers were rebuilt with `docker compose -f docker-compose.app.yml --env-file .env up -d --build --force-recreate`.

---

## Files touched

- `agentic-project/frontend/src/api/client.ts`
- `agentic-project/frontend/src/stores/sessionStore.ts`
- `agentic-project/frontend/src/sections/IotRegistryPage.tsx`
- `agentic-project/backend/api.py`
- `agentic-project/backend/llm_client.py`
- `agentic-project/docker-compose.app.yml`

---

## Still by design / deferred (not changed here)

| Topic | Note |
|-------|------|
| ID-only login | Still no passwords/tokens; knowing another user’s ID can impersonate on a trusted LAN |
| Parallel multi-file upload | Deferred (sequential upload remains) |
| OutputPanel 30s `forceUpdate` | Deferred |
| N+1 sample queries / large state_json rows | Deferred |
| Unused `_handle_direct` | Deferred (harmless) |
| DGX Postgres down | Runtime: backend waits on `DGX_HOST:5432`; app cannot fully start until Postgres is reachable |

---

## How to verify

1. Ensure DGX Postgres is up (`192.168.1.208:5432` or current `DGX_HOST`).
2. Open `http://n5407:7008`, hard-refresh, log in.
3. Confirm session card appears; type a question; Send enables and completes.
4. Progress steps should poll without `400` on `user_id`.
5. Backend direct port from another LAN machine should **not** be open (`7010` is localhost-only on the app host).
