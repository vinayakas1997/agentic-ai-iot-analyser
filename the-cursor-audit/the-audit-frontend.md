# Frontend audit findings

Verified against code under `agentic-project/frontend/src` (plus `nginx.conf` / compose for `VITE_API_URL`). Only issues confirmed in source are listed.

---

## Critical

### 1. 20s loading watchdog aborts long LLM turns
**File:** `stores/sessionStore.ts` (lines 558–571)  
**Behavior:** Any transition to `loading: true` schedules a 20s timer that forces `loading: false` and sets `error: "Request timed out — please try again"`. Chat/SQL/`sendMessage` often exceeds 20s.  
**Impact:** Composer unlocks mid-flight; user can send again; first request may still complete and mutate state. Timeout text is also never rendered (see #4).  
**Fix:** Scope the watchdog to bootstrap/switch only, or use a much higher timeout / AbortController tied to real request cancellation. Do not clear `loading` while `sendUserMessage` is still awaiting.

### 2. `refreshSessions()` after send wipes the session list
**File:** `stores/sessionStore.ts` line 434 — `await get().refreshSessions()` with no `userId`  
**Backend:** `list_sessions` returns `[]` when `user_id` is empty (`backend/api.py` 714–717).  
**Impact:** After every successful message, `sessions` becomes `[]` until the 15s poller (which does pass `userId`) restores it. Navbar count/list briefly or permanently looks empty if poller is broken.  
**Fix:** `await get().refreshSessions(useAuthStore.getState().userId || undefined)`.

### 3. `docker-compose.yml` default `VITE_API_URL=http://localhost:7010`
**Files:** `docker-compose.yml` line 46; contrast `docker-compose.app.yml` / `.env` (`VITE_API_URL=` empty) and `api/client.ts` line 1–2  
**Behavior:** Built assets call the **browser’s** localhost:7010, not the host serving the UI. Breaks LAN `http://hostname:7008`.  
**Fix:** Default empty (same-origin via nginx) like `docker-compose.app.yml`; never bake `localhost:7010` into production builds.

---

## High

### 4. `sessionStore.error` is never shown in the UI
**Files:** `stores/sessionStore.ts` (`set({ error })` in bootstrap/switch/send/timeout); no component reads `useSessionStore(s => s.error)`  
**Impact:** Bootstrap failure → `sessionId` stays `null`, send disabled (`ChatSection` `!sessionId`), no visible error. Send failures clear `pendingTurn` and throw; `handleSend` has no `try/catch` and already cleared the input (line 437).  
**Fix:** Surface `error` in Chat/Navbar; restore input on failure; catch in `handleSend` / aim runners.

### 5. `switchSession` does not clear `isLocalSession`
**File:** `stores/sessionStore.ts` `switchSession` set block (246–257) — sets `sessionId`/`sessionMeta` but not `isLocalSession: false` or `pendingTitle: null`  
**Impact:** New local session → switch to existing session → next `sendUserMessage` still sees `isLocalSession === true` and calls `createSession` again (340–350).  
**Fix:** Always set `isLocalSession: false`, `pendingTitle: null` when loading a server session.

### 6. `clearAll` nulls `_pollTimer` without `clearInterval`
**File:** `stores/sessionStore.ts` `clearAll` (124–125); used by `authStore.login` / `logout`  
**Impact:** Interval keeps running; `stopPoller` can no longer clear it (reference lost). Leaked timers after login/logout; StrictMode remount cannot clean up.  
**Fix:** Call `stopPoller()` / `clearInterval(_pollTimer)` inside `clearAll`.

### 7. Clipboard API without secure-context guard
**File:** `sections/QueryActions.tsx` line 520 — `navigator.clipboard.writeText(...)` with no `try/catch` / fallback  
**Impact:** On `http://hostname:port` (non-localhost), Clipboard API fails; unhandled rejection on Copy SQL. Same class of bug as `crypto.randomUUID` (already mitigated in `lib/id.ts`).  
**Fix:** `try/catch` + fallback (`textarea` + `document.execCommand('copy')`) when `!window.isSecureContext`.

### 8. Attached personal datasets dropped on bootstrap/switch
**Files:** `sessionStore.ts` bootstrap (197–202) and `switchSession` (261–268) — validate attached names only via `api.listDatasets()`  
**Impact:** Uploaded/personal names are filtered out; session reload loses personal attachments. ChatSection loads personal into lookup; restore path does not.  
**Fix:** Also load `listUserDatasets(uid)` when validating attached names.

### 9. Nginx `/api/` has no long `proxy_read_timeout`
**File:** `frontend/nginx.conf` `location /api/` (19–23)  
**Impact:** Default nginx read timeout (~60s) can 504 long LLM/`/messages` calls when using same-origin proxy (the recommended LAN setup).  
**Fix:** Set `proxy_read_timeout` / `proxy_send_timeout` high enough for LLM (e.g. 300–600s).

### 10. Bootstrap race: no generation/abort token
**Files:** `App.tsx` 47–49; `authStore.login` clears then sets `role`; `bootstrap` async  
**Impact:** Overlapping bootstraps (re-login, logout mid-flight) can apply stale `set({ sessionId, turns, ... })` after `clearAll`.  
**Fix:** Increment a bootstrap epoch / AbortController; ignore results if epoch mismatch.

---

## Medium

### 11. Clarify “Skip” advances without `confirmUploadDataset`
**File:** `ColumnClarifyView.tsx` 390–404 — requires `canProceed` but only bumps `index`  
**Impact:** Backend draft left unconfirmed; meanings discarded; orphaned upload rows.  
**Fix:** Confirm before next, or rename and explicitly abandon/delete the draft.

### 12. Local-session PATCH spam / 404s
**Files:** `ChatSection.tsx` 429–432 (`selected_aims` on every change); `persistTurns` 314–338  
**Impact:** While `isLocalSession` / temp `sessionId`, PATCH hits non-existent session (403/404). Noise and possible confusion.  
**Fix:** Guard with `!isLocalSession` (or only after `createSession`).

### 13. Context “selected datasets” ignores personal datasets
**File:** `ContextSection.tsx` 47–49, 119–129 — `datasetLookup` from `listDatasets()` only  
**Impact:** After upload, names are in `storeSelected` but filtered out of the selected list UI (ChatSection merges personal correctly).  
**Fix:** Merge `listUserDatasets` into lookup like ChatSection.

### 14. OutputPanel dataset checks ignore personal datasets
**File:** `OutputPanel.tsx` 65–67, 56–63, 86–90 — only `listDatasets()`  
**Impact:** Summarize / run proposal with personal datasets: treated as missing; warn/skip.  
**Fix:** Include user datasets in lookup.

### 15. Progress poller starts before auth
**File:** `App.tsx` 42–45 — `startPoller()` always; poller uses `userId` (`sessionStore` 530–547)  
**Impact:** Pre-login polls return `[]` (benign) but waste requests; after `clearAll` poller may be unstoppable (#6).  
**Fix:** Start poller only when `role`/`userId` is set; stop on logout.

### 16. `newSession` leaves `sessionStore.outputResults` stale
**File:** `sessionStore.ts` 277–297 — clears `useOutputStore` but not `outputResults` in session state  
**Impact:** Divergent copies of output results.  
**Fix:** Clear `outputResults: []` in the same `set`.

### 17. Hardcoded English for LLM-facing / status UX
| Location | Strings |
|----------|---------|
| `ProcessingPanel.tsx` 14–33, 52 | Step labels, “Processing...” |
| `sessionStore.ts` 323, 341, 366, 372, 565 | Status/toast/timeout English |
| `OutputPanel.tsx` 76 | Summarize prompt always English |
| `ColumnClarifyView.tsx` 152, 179, 368 | Fallbacks / “N columns still need…” |
| `EditColumnsDialog.tsx` | Entire dialog mostly English (title, LLM fill, errors) despite `useT` |
| `ContextSection.tsx` 333 | `title="Edit column meanings"` |

**Fix:** Route through `translations.ts` (ja/en); pass UI `language` into summarize prompt construction if required.

### 18. Upload: sequential one-file requests; clarify only after all finish
**File:** `ChatSection.tsx` `handleCsvFilesSelected` 555–585  
**Impact:** Multi-file uploads are slow; overlay stays up for the whole batch; no cancel. Acceptable but fragile on flaky LAN.  
**Fix:** Optional parallel with concurrency limit; allow cancel; open clarify as drafts arrive.

---

## Low

### 19. `ColumnClarifyView` resize `useEffect` has no dependency array
**File:** `ColumnClarifyView.tsx` 35–44 — runs every render  
**Fix:** Depend on `[index, columns, pendingDrafts]` or resize on input only.

### 20. OutputPanel 30s `forceUpdate` interval
**File:** `OutputPanel.tsx` 36–38 — re-renders whole panel for relative time  
**Fix:** Update only visible timestamps or use a lighter tick.

### 21. Dead axios-shaped error helper
**File:** `sessionStore.ts` 34–45 — client uses `fetch`/`ApiError`, not axios  
**Fix:** Parse `ApiError` body JSON `detail` if present.

### 22. Brand / chrome not localized
**Files:** `LoginPage.tsx` 45; `Navbar.tsx` 57 (“AGI DATA ANALYSER”, “NOTE:”)  
**Fix:** i18n keys if JA UI should be complete.

### 23. `crypto.randomUUID` already mitigated
**File:** `lib/id.ts` — fallback for non-secure contexts. Toast/output IDs use `newId()`. No remaining direct `crypto.randomUUID` in `src`.

### 24. Same-origin API pattern (when `VITE_API_URL` empty) is correct
**File:** `api/client.ts` + nginx `/api/` proxy — good for LAN/CORS. Risk is only when compose/docs force `localhost:7010` (#3).

---

## Summary by theme

| Theme | Worst issues |
|-------|----------------|
| Secure context / LAN HTTP | Clipboard (#7); UUID already fixed; compose localhost API (#3) |
| Session/auth races | Bootstrap overlap (#10); `clearAll` poller (#6); login→bootstrap OK if #10 fixed |
| Broken UI state | Invisible errors (#4); 20s timeout (#1); null `sessionId` after failed bootstrap |
| CORS / base URL | Empty `VITE_API_URL` good; `docker-compose.yml` default bad (#3); nginx LLM timeout (#9) |
| i18n / LLM UX | ProcessingPanel, EditColumns, status strings, summarize prompt (#17) |
| Upload | Skip without confirm (#11); personal attach restore (#8, #13) |
| Inefficiency | Unscoped `refreshSessions` (#2); pre-login poller (#15); clarify effect (#19) |

I did not invent service-worker/geolocation issues — none appear in this frontend.